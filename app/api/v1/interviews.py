import base64
import traceback
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.interview_repository import InterviewRepository
from app.schemas.interview import InterviewSessionStartOut
from app.services.interview_director import InterviewDirector
from app.services import stt_service
from app.background_tasks import run_interview_analysis

router = APIRouter()


@router.post(
    "/applications/{application_id}/start-interview",
    response_model=InterviewSessionStartOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сессию интервью для отклика"
)
def start_interview_session(application_id: int, db: Session = Depends(get_db)):
    # Упрощенный эндпоинт для тестов. В проде потребуется аутентификация кандидата.
    interview_repo = InterviewRepository(db)
    application = interview_repo.get_application_by_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.interview_session:
        raise HTTPException(status_code=400, detail="Interview session already exists for this application")

    interview_session = interview_repo.create_interview_session(application_id=application_id)
    return {"interview_session_id": interview_session.id, "status": interview_session.status}


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
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = Depends()
):
    await websocket.accept()

    director = None # Объявляем здесь, чтобы был доступен в finally
    try:
        director = InterviewDirector(session_id=session_id, db=db)
    except ValueError as e:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
        return

    try:
        # Старт диалога
        audio_data, text = await director.start()
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})

        # Основной цикл диалога
        audio_generator = audio_stream_from_websocket(websocket)
        full_candidate_response = ""
        async for result in stt_service.recognize_stream(audio_generator):
            await websocket.send_json(result)

            if result.get("type") in ["final", "final_refinement"]:
                full_candidate_response += result.get("text", "") + " "

            if result.get("type") == "final":
                clean_response = full_candidate_response.strip()
                if clean_response:
                    audio_data, text = await director.handle_candidate_response(clean_response)
                    if audio_data:
                        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                        await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})

                    # Проверяем, не пора ли заканчивать
                    if director.is_interview_finished():
                        await director.say_goodbye() # Предполагаем, что директор может сказать прощальную фразу
                        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                        break # Выходим из цикла, чтобы попасть в finally

                    full_candidate_response = ""

    except WebSocketDisconnect:
        print(f"Клиент отключился от сессии {session_id}.")
    except Exception as e:
        print(f"Необработанная ошибка в WebSocket для сессии {session_id}:")
        traceback.print_exc()
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=f"An internal error occurred: {e}")
    finally:
        print(f"Соединение WebSocket для сессии {session_id} закрыто. Финализация...")
        if director:
            # Обновляем статус сессии в БД (COMPLETED или ERROR)
            director.end_interview()
            # Запускаем фоновую задачу анализа
            background_tasks.add_task(
                run_interview_analysis,
                session_id=director.session_id,
                is_completed_correctly=director.is_finished_correctly
            )
            print(f"Фоновая задача анализа для сессии {director.session_id} запланирована.")