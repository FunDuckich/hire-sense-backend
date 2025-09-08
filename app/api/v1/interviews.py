import base64
import traceback
import asyncio
import json
from datetime import datetime
import pytz
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.interview import InterviewStatus, TranscriptRole
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.repositories.application_repository import ApplicationRepository
from app.models.application import ApplicationStatus
from app.schemas.interview import InterviewSessionStartOut
from app.services.interview_director import InterviewDirector
from app.services import stt_service, tts_service, llm_service
from app.background_tasks import run_interview_analysis
from app.api.dependencies import get_db, get_current_candidate_user, \
    get_current_user_ws  # get_current_candidate_user здесь уже не используется напрямую, но пусть будет

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

    now_utc = datetime.now(pytz.utc)
    expires_at_utc = session.expires_at.replace(tzinfo=pytz.utc)

    if now_utc > expires_at_utc:
        app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="The invitation to this interview has expired.")

    return {"interview_session_id": session.id, "status": session.status}


async def _send_avatar_speech(websocket: WebSocket, text: str):
    try:
        # Используем asyncio.to_thread для запуска синхронной функции tts_service.synthesize_speech в отдельном потоке
        audio_data = await asyncio.to_thread(tts_service.synthesize_speech, text)
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({
                "type": "avatar_speech",
                "text": text,
                "audio_b64": audio_b64
            })
    except Exception as e:
        print(f"Ошибка при отправке речи аватара: {e}")


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

        text_to_say = director.start()

        await _send_avatar_speech(websocket, text_to_say)

        while not (director.is_finished_correctly or director.force_terminated):
            audio_chunks = []
            has_started_speaking = False

            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(),
                                                     timeout=settings.CANDIDATE_SILENCE_TIMEOUT_SECONDS)
                    if "bytes" in message:
                        has_started_speaking = True
                        audio_chunks.append(message["bytes"])
                    elif "text" in message:
                        data = json.loads(message["text"])
                        if data.get("type") == "stream_end":
                            break
                except asyncio.TimeoutError:
                    if not has_started_speaking and websocket.client_state == WebSocketState.CONNECTED:
                        print("[WebSocket] Кандидат долго молчит. Отправка поддерживающей фразы.")
                        text_to_say_support = llm_service.generate_support_phrase(director.dialogue_history)
                        director._record_message(text_to_say_support, TranscriptRole.AVATAR)
                        await _send_avatar_speech(websocket, text_to_say_support)
                    else:
                        break

            recognized_text = None
            if audio_chunks:
                final_text_parts = []

                async def audio_generator():
                    for chunk in audio_chunks:
                        yield chunk

                async for result in stt_service.recognize_stream(audio_generator()):
                    await websocket.send_json(result)
                    event_type = result.get("type")
                    text = result.get("text", "")

                    if event_type == "final":
                        final_text_parts.append(text)
                    elif event_type == "final_refinement":
                        if final_text_parts:
                            final_text_parts[-1] = text
                        else:
                            final_text_parts.append(text)

                recognized_text = " ".join(final_text_parts).strip()

            if recognized_text:
                text_to_say_next = director.handle_candidate_response(recognized_text)
            else:
                text_to_say_next = "Извините, я вас не расслышал. Можете повторить, пожалуйста?"

            await _send_avatar_speech(websocket, text_to_say_next)

        print("Основной цикл диалога завершен. Отправка сигнала о закрытии клиенту.")
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)

    except WebSocketDisconnect as e:
        print(f"Клиент отключился от сессии {session_id} с кодом {e.code}.")
    except Exception as e:
        print(f"Необработанная ошибка в WebSocket для сессии {session_id}:")
        traceback.print_exc()
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
    finally:
        print(f"Финализация сессии {session_id}...")
        if director:
            session = director.interview_repo.update_session_completion_status(
                session_id=session_id,
                is_completed_correctly=director.is_finished_correctly
            )
            if session:
                background_tasks.add_task(
                    run_interview_analysis,
                    session.id,
                    session.is_completed_correctly
                )
                print(f"Фоновая задача анализа для сессии {session_id} запланирована.")
        db.close()
