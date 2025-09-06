import base64
import traceback
import asyncio
import json
from datetime import datetime
import pytz
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.repositories.interview_repository import InterviewRepository
from app.repositories.application_repository import ApplicationRepository
from app.models.application import ApplicationStatus
from app.schemas.interview import InterviewSessionStartOut
from app.services.interview_director import InterviewDirector
from app.services import stt_service, tts_service
from app.background_tasks import run_interview_analysis
from app.api.dependencies import get_db, get_current_candidate_user, get_current_user_ws
from app.models.user import User
from app.models.interview import InterviewStatus

router = APIRouter()


@router.post(
    "/applications/{application_id}/start-interview",
    response_model=InterviewSessionStartOut,
    status_code=status.HTTP_200_OK,
    summary="Проверить и начать сессию интервью для отклика"
)
def start_interview_session(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    app_repo = ApplicationRepository(db)
    application = app_repo.get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this application")

    session = application.interview_session
    if not session:
        raise HTTPException(status_code=404, detail="Interview session has not been created for this application yet.")

    if datetime.now(pytz.utc) > session.expires_at:
        app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="The invitation to this interview has expired.")

    return {"interview_session_id": session.id, "status": session.status}


async def audio_stream_from_websocket(websocket: WebSocket):
    try:
        while True:
            yield await websocket.receive_bytes()
    except WebSocketDisconnect:
        return


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        session_id: int,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    db: Session = SessionLocal()
    director = None

    try:
        interview_repo = InterviewRepository(db)
        session = interview_repo.get_session_with_details(session_id)

        if not session or session.application.user_id != current_user.id or session.status != InterviewStatus.SCHEDULED:
            reason = "Interview session not found, not authorized, or has invalid status."
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=reason)
            return

        print(f"User {current_user.email} successfully connected to WebSocket session {session_id}.")
        director = InterviewDirector(session_id=session_id, db=db)

        audio_data, text = await director.start()
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})

        while not director.is_finished_correctly:

            audio_chunks = []
            has_started_speaking = False
            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(), timeout=10.0)

                    if "bytes" in message:
                        has_started_speaking = True
                        audio_chunks.append(message["bytes"])
                    elif "text" in message:
                        try:
                            data = json.loads(message["text"])
                            if data.get("type") == "stream_end":
                                break
                        except json.JSONDecodeError:
                            print(f"Получено не-JSON текстовое сообщение: {message['text']}")

                except asyncio.TimeoutError:
                    if not has_started_speaking:
                        print("[WebSocket] Кандидат долго молчит. Отправка поддерживающей фразы.")
                        text_to_say = "Не торопитесь, я подожду. Пожалуйста, соберитесь с мыслями."
                        audio_data = tts_service.synthesize_speech(text_to_say)
                        if audio_data:
                            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                            await websocket.send_json(
                                {"type": "avatar_speech", "text": text_to_say, "audio_b64": audio_b64})
                    else:
                        print("[WebSocket] Длинная пауза в середине речи. Считаем фразу оконченной.")
                        break

            recognized_text = ""
            if audio_chunks:
                async def audio_generator():
                    for chunk in audio_chunks:
                        yield chunk

                async for result in stt_service.recognize_stream(audio_generator()):
                    await websocket.send_json(result)
                    if result.get("type") in ["final", "final_refinement"]:
                        recognized_text += result.get("text", "") + " "
                recognized_text = recognized_text.strip()

            if recognized_text:
                audio_data, text = await director.handle_candidate_response(recognized_text)
                if audio_data:
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                    await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})
            else:
                text_to_say = "Извините, я вас не расслышал. Можете повторить, пожалуйста?"
                audio_data = tts_service.synthesize_speech(text_to_say)
                if audio_data:
                    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                    await websocket.send_json({"type": "avatar_speech", "text": text_to_say, "audio_b64": audio_b64})

    except WebSocketDisconnect as e:
        print(f"Клиент отключился от сессии {session_id} с кодом {e.code}.")
    except Exception as e:
        print(f"Необработанная ошибка в WebSocket для сессии {session_id}:")
        traceback.print_exc()
        if websocket.client_state.name != 'DISCONNECTED':
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        print(f"Финализация сессии {session_id}...")
        if director:
            session = director.interview_repo.update_session_completion_status(
                session_id=session_id,
                is_completed_correctly=director.is_finished_correctly
            )
            if session:
                # --- ВРЕМЕННЫЕ ИЗМЕНЕНИЯ ДЛЯ ОТЛАДКИ ---
                print("!!! ОТЛАДКА: Запускаем анализ СИНХРОННО, чтобы увидеть ошибки !!!")
                # background_tasks.add_task(
                #     run_interview_analysis,
                #     session.id,
                #     session.is_completed_correctly
                # )
                run_interview_analysis(session.id, session.is_completed_correctly)
                print("!!! ОТЛАДКА: Синхронный анализ завершен !!!")
                # --- КОНЕЦ ВРЕМЕННЫХ ИЗМЕНЕНИЙ ---

                print(f"Фоновая задача анализа для сессии {session_id} запланирована.")

        db.close()
