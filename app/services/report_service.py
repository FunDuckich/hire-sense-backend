from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.models.application import Application
from app.schemas.screening import ScreeningReportOut


class ReportService:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader("templates"))
        self.template = self.env.get_template("report_template.html")

    def generate_pdf_report(self, application: Application) -> bytes:
        if not application.screening_result:
            raise ValueError("Отчет по скринингу для этой заявки еще не готов.")

        report_data = ScreeningReportOut.model_validate(application.screening_result.result_json)

        html_out = self.template.render(
            application=application,
            report=report_data
        )

        pdf_bytes = HTML(string=html_out).write_pdf()
        return pdf_bytes


report_service = ReportService()
