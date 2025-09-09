import asyncio
import base64
import json
import traceback
from datetime import datetime
import pytz
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.core.database import SessionLocal
from app.api.dependencies import get_db, get_current_candidate_user, get_current_user_ws
from app.background_tasks import run_interview_analysis
from app.models.application import ApplicationStatus
from app.models.interview import InterviewStatus, TranscriptRole
from app.models.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.interview_repository import InterviewRepository
from app.schemas.interview import InterviewSessionStartOut
from app.services.interview_director import InterviewDirector
from app.services.stt_service import StreamRecognizer
from app.services import tts_service

router = APIRouter()


@router.post("/applications/{application_id}/start-interview", response_model=InterviewSessionStartOut)
async def start_interview_session(
        application_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    app_repo = ApplicationRepository(db)
    application = await app_repo.get_application_by_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this application")

    session = application.interview_session
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not created yet.")

    now_utc = datetime.now(pytz.utc)
    if now_utc > session.expires_at.replace(tzinfo=pytz.utc):
        await app_repo.update_application_status(application_id, ApplicationStatus.REJECTED)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="The invitation has expired.")

    return {"interview_session_id": session.id, "status": session.status}


async def _send_avatar_speech(websocket: WebSocket, text: str):
    try:
        if text and websocket.client_state == WebSocketState.CONNECTED:
            audio_data = await asyncio.to_thread(tts_service.synthesize_speech, text)
            if audio_data and websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "avatar_speech",
                    "text": text,
                    "audio_b64": base64.b64encode(audio_data).decode('utf-8')
                })
    except Exception as e:
        print(f"Error in _send_avatar_speech: {e}")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        session_id: int,
        current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    db: AsyncSession = SessionLocal()
    director, recognizer = None, None
    try:
        interview_repo = InterviewRepository(db)
        session = await interview_repo.get_session_with_details(session_id)
        if not session or session.application.user_id != current_user.id or session.status != InterviewStatus.SCHEDULED:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        director = InterviewDirector(session_id=session_id, db=db)
        await director.initialize()

        recognizer = StreamRecognizer()
        await _send_avatar_speech(websocket, await director.start())

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

            has_spoken = False
            silence_iterations = 0

            while True:
                try:
                    message = await asyncio.wait_for(websocket.receive(),
                                                     timeout=settings.WEBSOCKET_RECEIVE_TIMEOUT_SECONDS)
                    if "bytes" in message and len(message.get("bytes", b'')) > 0:
                        has_spoken = True
                        silence_iterations = 0
                        await audio_chunk_queue.put(message["bytes"])
                    elif "text" in message:
                        if json.loads(message["text"]).get("type") == "user_speech_end":
                            break
                except asyncio.TimeoutError:
                    silence_iterations += 1
                    if has_spoken and silence_iterations >= settings.MAX_SILENCE_ITERATIONS_BEFORE_BREAK:
                        break
                    elif not has_spoken and director.silence_count + silence_iterations >= director.MAX_SILENCE_PROMPTS:
                        await audio_chunk_queue.put(None)
                        await recognition_task
                        text_to_say = await director.handle_candidate_silence()
                        await _send_avatar_speech(websocket, text_to_say)
                        if director.force_terminated:
                            break
                        has_spoken = "silence_handled"
                        break
                except WebSocketDisconnect:
                    break

            if director.force_terminated:
                break

            await audio_chunk_queue.put(None)
            await recognition_task

            if not has_spoken or has_spoken == "silence_handled":
                continue

            final_text_parts = []
            for res in stt_results:
                event_type, text = res.get("type"), res.get("text", "")
                if event_type == "final":
                    final_text_parts.append(text)
                elif event_type == "final_refinement":
                    if final_text_parts:
                        final_text_parts[-1] = text
                    else:
                        final_text_parts.append(text)

            recognized_text = " ".join(final_text_parts).strip()

            if recognized_text:
                text_to_say = await director.handle_candidate_response(recognized_text)
            else:
                text_to_say = "Простите, я вас не расслышал. Можете повторить?"
                await director._record_message(text_to_say, TranscriptRole.AVATAR)

            await _send_avatar_speech(websocket, text_to_say)

    except (WebSocketDisconnect, asyncio.CancelledError):
        print(f"Connection gracefully closed for session {session_id}")
    except Exception:
        print(f"Unhandled error in WebSocket for session {session_id}:")
        traceback.print_exc()
    finally:
        if recognizer:
            await recognizer.close()
        if director:
            await director.finalize_session()

            def run_analysis_sync():
                run_interview_analysis(session_id, director.is_finished_correctly)

            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, run_analysis_sync)
        await db.close()
        print(f"Session {session_id} finalized.")