from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import Response
from app.models.user import User
from app.api.dependencies import get_db, get_current_hr_user
from app.repositories.application_repository import ApplicationRepository
from app.services.report_service import report_service

router = APIRouter()


@router.get("/applications/{application_id}/report/download")
def download_screening_report(
        application_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_hr_user)
):
    app_repo = ApplicationRepository(db)
    application = app_repo.get_application_by_id(application_id=application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.vacancy.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this report")
    if not application.screening_result:
        raise HTTPException(status_code=404, detail="Screening report not found for this application")

    try:
        pdf_bytes = report_service.generate_pdf_report(application)

        filename = f"report_candidate_{application.candidate.id}_vacancy_{application.vacancy.id}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Ошибка при генерации PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report.")
