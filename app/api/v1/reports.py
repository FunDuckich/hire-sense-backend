from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_db, get_current_hr_user
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.interview import InterviewTranscriptOut
from app.schemas.report import InterviewReportOut

router = APIRouter()


@router.get("/interviews/{session_id}/report", response_model=InterviewReportOut)
async def get_interview_report(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_hr_user),
):
    report_repo = ReportRepository(db)
    interview_repo = InterviewRepository(db)

    report = await report_repo.get_report_by_session_id(session_id)

    if report:
        session = await interview_repo.get_session_with_details(session_id)
        if not session or session.application.vacancy.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this report")
        return report

    session = await interview_repo.get_session_with_details(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this report")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report for this interview is not ready yet")


@router.get("/interviews/{session_id}/transcript", response_model=InterviewTranscriptOut)
async def get_interview_transcript(
        session_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_hr_user),
):
    interview_repo = InterviewRepository(db)
    session = await interview_repo.get_session_with_details(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this transcript")

    transcript = await interview_repo.get_transcript_for_session(session_id)
    return {"entries": transcript, "session_id": session_id}