from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_hr_user
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.schemas.report import InterviewReportOut
from app.schemas.interview import InterviewTranscriptOut

router = APIRouter()


@router.get(
    "/interviews/{session_id}/report",
    response_model=InterviewReportOut,
    summary="Получить отчет по результатам интервью"
)
def get_interview_report(
        session_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user),
):
    interview_repo = InterviewRepository(db)
    session = interview_repo.get_session_with_details(session_id)

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    if session.application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this report")

    if not session.report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report for this interview is not ready yet")

    return session.report


@router.get(
    "/interviews/{session_id}/transcript",
    response_model=InterviewTranscriptOut,
    summary="Получить полную транскрипцию интервью"
)
def get_interview_transcript(
        session_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user),
):
    interview_repo = InterviewRepository(db)
    session = interview_repo.get_session_with_details(session_id)

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    if session.application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this transcript")

    transcript_entries = interview_repo.get_transcript_for_session(session_id)

    return InterviewTranscriptOut(session_id=session_id, entries=transcript_entries)
