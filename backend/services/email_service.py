import smtplib
from email.message import EmailMessage

from backend.config import Settings


class EmailService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.smtp_host and self.settings.smtp_username and self.settings.smtp_password)

    def send_password_reset_email(self, to_email: str, reset_link: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Reset your AI Image Generator password"
        message["From"] = self.settings.mail_from
        message["To"] = to_email
        message.set_content(
            """
Hello,

We received a password reset request for your account.

Use this reset link:
{reset_link}

If you did not request this, you can ignore this email.
""".strip().format(reset_link=reset_link)
        )

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
