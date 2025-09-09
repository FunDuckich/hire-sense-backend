from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_db, get_current_hr_user, get_current_candidate_user
from app.models.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.report_repository import ReportRepository
from app.schemas.report import InterviewReportOut, CandidateFeedbackOut
from app.schemas.interview import InterviewTranscriptOut

router = APIRouter()


@router.get(
    "/applications/{application_id}/feedback",
    response_model=CandidateFeedbackOut,
    summary="Get feedback for the candidate after an interview"
)
def get_interview_feedback_for_candidate(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_candidate_user)
):
    app_repo = ApplicationRepository(db)
    application = app_repo.get_application_with_report(application_id)

    if not application or application.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Application not found for the current user.")

    if not application.interview_report:
        raise HTTPException(status_code=404, detail="Feedback is not ready yet.")

    feedback_data = application.interview_report.analysis_result.get("candidate_feedback")

    if not feedback_data:
        return CandidateFeedbackOut()

    return CandidateFeedbackOut(**feedback_data)


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
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this report")

    report_repo = ReportRepository(db)
    report = report_repo.get_report_by_session_id(session_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report for this interview is not ready yet")

    return report


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
