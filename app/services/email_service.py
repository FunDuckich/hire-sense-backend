import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.models.application import Application


class EmailService:
    def _send_email(self, to_email: str, subject: str, body_html: str):
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.EMAIL_SENDER
        message["To"] = to_email
        message.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_SENDER, to_email, message.as_string())
            print(f"Письмо успешно отправлено на {to_email}")
        except Exception as e:
            print(f"Ошибка при отправке письма: {e}")

    def send_invitation_email(self, application: Application):
        candidate_name = application.candidate.name
        vacancy_title = application.vacancy.job_title
        # TODO: Заменить URL на реальный URL фронтенда
        interview_link = f"http://localhost:3000/interview/start/{application.id}"

        subject = f"Приглашение на AI-интервью на позицию '{vacancy_title}'"
        body_html = f"""
        <html>
        <body>
            <h2>Уважаемый {candidate_name},</h2>
            <p>Мы рассмотрели ваше резюме на позицию '{vacancy_title}' и хотели бы пригласить вас на следующий этап — автоматизированное AI-интервью.</p>
            <p>Интервью займет около 20-30 минут. Пожалуйста, убедитесь, что у вас есть стабильное интернет-соединение и тихое место.</p>
            <p>Чтобы начать, перейдите по ссылке: <a href="{interview_link}">{interview_link}</a></p>
            <p>С уважением,<br>HR-команда</p>
        </body>
        </html>
        """
        self._send_email(to_email=application.candidate.email, subject=subject, body_html=body_html)

    def send_rejection_email(self, application: Application):
        candidate_name = application.candidate.name
        vacancy_title = application.vacancy.job_title

        subject = f"Ответ по вакансии '{vacancy_title}'"
        body_html = f"""
        <html>
        <body>
            <h2>Уважаемый {candidate_name},</h2>
            <p>Благодарим вас за интерес, проявленный к вакансии '{vacancy_title}'.</p>
            <p>Мы внимательно ознакомились с вашим резюме, но на данный момент не готовы сделать вам предложение. Мы сохраним ваше резюме в нашей базе и свяжемся с вами, если появятся подходящие вакансии.</p>
            <p>Желаем вам успехов в поиске работы!</p>
            <p>С уважением,<br>HR-команда</p>
        </body>
        </html>
        """
        self._send_email(to_email=application.candidate.email, subject=subject, body_html=body_html)


email_service = EmailService()
