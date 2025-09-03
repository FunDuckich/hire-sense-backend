import base64
import asyncio
import traceback
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.api.dependencies import get_db, get_current_candidate_user
from app.repositories.interview_repository import InterviewRepository
from app.schemas.interview import InterviewSessionStartOut

from app.services.interview_director import InterviewDirector
from app.services import stt_service

router = APIRouter()


# --- Зависимости, специфичные для этого роутера ---

def get_current_candidate_user(current_user: User = Depends(get_db)) -> User:
    from app.api.dependencies import get_current_user
    current_user = Depends(get_current_user)
    if current_user.role != "CANDIDATE":
        raise HTTPException(status_code=403, detail="The user doesn't have enough privileges")
    return current_user


@router.post(
    "/applications/{application_id}/start-interview",
    response_model=InterviewSessionStartOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Interviews"]
)
def start_interview_session(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    """
    Создает новую сессию интервью для существующей заявки.
    Доступно только кандидату, который является владельцем заявки.
    Возвращает ID созданной сессии, который используется для подключения к WebSocket.
    """
    interview_repo = InterviewRepository(db)

    application = interview_repo.get_application_by_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to start this interview for this application")

    if application.interview_session:
        raise HTTPException(status_code=400, detail="Interview session already exists for this application")

    interview_session = interview_repo.create_interview_session(application_id=application_id)

    return {"interview_session_id": interview_session.id, "status": interview_session.status}


# --- WebSocket Эндпоинт ---

async def audio_stream_from_websocket(websocket: WebSocket):
    """Асинхронный генератор, который читает аудио-байты из WebSocket."""
    try:
        while True:
            yield await websocket.receive_bytes()
    except WebSocketDisconnect:
        print("Клиент отключился, генератор аудиопотока завершает работу.")
        return


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: int,
    db: Session = Depends(get_db)
):
    await websocket.accept()
    try:
        director = InterviewDirector(session_id=session_id, db=db)
    except ValueError as e:
        print(f"Ошибка инициализации InterviewDirector: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
        return

    try:
        audio_data, text = await director.start()
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})

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

                    full_candidate_response = ""

    except WebSocketDisconnect:
        print(f"Клиент отключился от сессии {session_id}. Запускаем финальный анализ.")
        session = director.interview_repo.update_session_completion_status(
            session_id=session_id,
            is_completed_correctly=director.is_finished_correctly
        )
        background_tasks.add_task(run_interview_analysis, session.id, session.is_completed_correctly)
    except Exception as e:
        print(f"Необработанная ошибка в WebSocket для сессии {session_id}:")
        traceback.print_exc()
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=f"An internal error occurred: {e}")
    finally:
        print(f"Соединение WebSocket для сессии {session_id} закрыто.")