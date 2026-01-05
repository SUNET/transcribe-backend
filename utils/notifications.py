import collections
import smtplib
import ssl
import threading

from utils.log import get_logger
from utils.settings import get_settings


logger = get_logger()
settings = get_settings()


class Notifications:
    def __init__(self) -> None:
        """
        Initialize the Notifications system.
        """

        self.__queue = collections.deque()

        def handler() -> None:
            threading.Timer(3.0, handler).start()

            while len(self.__queue) > 0:
                notification = self.__queue.popleft()

                if (
                    settings.API_SMTP_HOST
                    and settings.API_SMTP_USERNAME
                    and settings.API_SMTP_PASSWORD
                ):
                    self.__notification_send_email(
                        to_emails=notification["to_emails"],
                        subject=notification["subject"],
                        message=notification["message"],
                    )

        handler()

    def add(self, to_emails: list, subject: str, message: str) -> None:
        """
        Queue an email notification to be sent later.
        """

        if not settings.API_SMTP_HOST:
            logger.warning(
                "SMTP host is not configured. Email notifications will not be sent."
            )
            return

        self.__queue.append(
            {
                "to_emails": to_emails,
                "subject": subject,
                "message": message,
            }
        )

    def __notification_send_email(
        self, to_emails: list, subject: str, message: str
    ) -> None:
        """
        Send an email notification.
        """
        context = ssl.create_default_context()
        server = smtplib.SMTP(settings.API_SMTP_HOST, settings.API_SMTP_PORT)
        server.starttls(context=context)
        server.login(settings.API_SMTP_USERNAME, settings.API_SMTP_PASSWORD)

        for email in to_emails:
            mail_to_send = f"From: Sunet Scribe <{settings.API_SMTP_SENDER}>\nTo: {email}\nSubject: {subject}\n\n{message}"

            try:
                server.sendmail(settings.API_SMTP_SENDER, to_emails, mail_to_send)
                logger.info(f"Email sent to {', '.join(to_emails)}")
            except Exception as e:
                logger.error(f"Error sending email to {", ".join(to_emails)}: {e}")

    def send_email_verification(self, to_email: str) -> None:
        """
        Send an email verification notification.
        """

        subject = "Your e-mail address have been updated"
        message = """\
        Hello,

        Your e-mail address have been updated in Sunet Scribe.
        If you did not perform this action, please contact support.

        Best regards,
        Sunet Scribe Team
        """

        self.add(
            to_emails=[to_email],
            subject=subject,
            message=message,
        )

    def send_transcription_finished(self, to_email: str) -> None:
        """
        Send a transcription finished notification.
        """

        subject = "Your transcription job is finished"
        message = """\
        Hello,

        Your transcription job is finished.
        You can now log in to Sunet Scribe to see your transcription.

        Best regards,
        Sunet Scribe Team
        """

        self.add(
            to_emails=[to_email],
            subject=subject,
            message=message,
        )


notifications = Notifications()
