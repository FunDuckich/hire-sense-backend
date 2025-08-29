from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.api.dependencies import get_db
# Импортируем зависимость, которую мы создали в `applications.py`
from app.api.v1.applications import get_current_candidate_user
from app.repositories.interview_repository import InterviewRepository
from app.schemas.interview import InterviewSessionStartOut

import base64
from fastapi import WebSocket, WebSocketDisconnect
from app.services.interview_director import InterviewDirector
from app.services.stt_service import STTService
# TODO Предполагаем, что STT сервис будет импортироваться так

router = APIRouter()


@router.post(
    "/applications/{application_id}/start-interview",
    response_model=InterviewSessionStartOut,
    status_code=status.HTTP_201_CREATED
)
def start_interview_session(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    interview_repo = InterviewRepository(db)

    application = interview_repo.get_application_by_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to start this interview")

    if application.interview_session:
        raise HTTPException(status_code=400, detail="Interview session already exists for this application")

    interview_session = interview_repo.create_interview_session(application_id=application_id)

    return {"interview_session_id": interview_session.id, "status": interview_session.status}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        session_id: int,
        db: Session = Depends(get_db)
):
    await websocket.accept()

    # 1. Инициализация
    director = InterviewDirector(session_id=session_id, db=db)
    stt_service = STTService()  # Создаем экземпляр STT

    print(f"WebSocket connection accepted for session {session_id}")

    try:
        # 2. Начало интервью
        # Директор генерирует приветствие, мы отправляем его клиенту
        audio_data, text = await director.start()

        # Отправляем аудио в base64, чтобы его легко было обработать в JSON
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')
        await websocket.send_json({
            "type": "avatar_speech",
            "text": text,
            "audio_b64": audio_b64
        })

        # 3. Основной цикл: слушаем кандидата -> распознаем -> отвечаем
        # recognize_stream должен быть асинхронным генератором,
        # который принимает websocket и yield'ует распознанный текст
        async for recognized_text in stt_service.recognize_stream(websocket):
            if recognized_text:
                print(f"Recognized text: '{recognized_text}'")

                # Отправляем распознанный текст на фронт для отображения
                await websocket.send_json({
                    "type": "final_result",
                    "text": recognized_text
                })

                # Получаем ответ от "режиссера"
                audio_data, text = await director.handle_candidate_response(recognized_text)

                # Отправляем ответ аватара клиенту
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                await websocket.send_json({
                    "type": "avatar_speech",
                    "text": text,
                    "audio_b64": audio_b64
                })

    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")
    except Exception as e:
        print(f"An error occurred in session {session_id}: {e}")
        # Можно отправить сообщение об ошибке клиенту перед закрытием
        await websocket.close(code=1011, reason=f"An internal error occurred: {e}")
    finally:
        print(f"Closing connection for session {session_id}")