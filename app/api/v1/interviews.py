import base64
import asyncio
import json
from datetime import datetime
import pytz
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState
from app.core.database import SessionLocal
from app.models.interview import InterviewStatus, TranscriptRole
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.repositories.application_repository import ApplicationRepository
from app.models.application import ApplicationStatus
from app.schemas.interview import InterviewSessionStartOut
from app.services.interview_director import InterviewDirector
from app.services import tts_service
from app.background_tasks import run_interview_analysis
from app.api.dependencies import get_db, get_current_candidate_user, get_current_user_ws
from app.services.stt_service import StreamRecognizer
from app.core.config import settings

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
    if not text:
        return
    try:
        loop = asyncio.get_running_loop()
        audio_data = await loop.run_in_executor(None, tts_service.synthesize_speech, text)
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            await websocket.send_json({"type": "avatar_speech", "text": text, "audio_b64": audio_b64})
    except Exception as e:
        print(f"Error in _send_avatar_speech: {e}")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        session_id: int,
        current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    db: Session = SessionLocal()
    director, recognizer = None, None
    try:
        director = InterviewDirector(session_id=session_id, db=db)
        recognizer = StreamRecognizer()

        await _send_avatar_speech(websocket, director.start())

        while not director.is_finished_correctly and not director.force_terminated:

            audio_chunk_queue = asyncio.Queue()
            stt_results = []

            async def audio_generator():
                while True:
                    chunk = await audio_chunk_queue.get()
                    if chunk is None:
                        break
                    yield chunk

            async def recognition_task_func():
                async for result in recognizer.recognize(audio_generator()):
                    stt_results.append(result)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json(result)

            recognition_task = asyncio.create_task(recognition_task_func())

            while True:
                try:
                    message = await websocket.receive()
                    if "bytes" in message:
                        await audio_chunk_queue.put(message["bytes"])

                    last_result = stt_results[-1] if stt_results else None
                    if last_result and last_result.get("type") == "final_refinement":
                        print("[WS] Final refinement received from Yandex STT. Ending listen loop.")
                        break
                except WebSocketDisconnect:
                    break

            await audio_chunk_queue.put(None)
            await recognition_task

            if websocket.client_state != WebSocketState.CONNECTED:
                break

            final_text = "".join(r.get("text", "") for r in stt_results if r.get("type") == "final_refinement").strip()
            if not final_text:
                final_text = "".join(r.get("text", "") for r in stt_results if r.get("type") == "final").strip()

            if final_text:
                text_to_say = director.handle_candidate_response(final_text)
            else:
                text_to_say = director.handle_candidate_silence()

            await _send_avatar_speech(websocket, text_to_say)

    except (WebSocketDisconnect, asyncio.CancelledError):
        print(f"Connection gracefully closed for session {session_id}")
    finally:
        if recognizer:
            await recognizer.close()
        if director:
            director.finalize_session()

            def run_analysis_sync():
                run_interview_analysis(session_id, director.is_finished_correctly)

            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, run_analysis_sync)
        db.close()
        print(f"Session {session_id} finalized.")