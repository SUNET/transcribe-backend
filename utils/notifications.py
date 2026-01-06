import collections
import smtplib
import ssl
import threading

from db.models import NotificationsSent
from db.session import get_session
from utils.log import get_logger
from utils.settings import get_settings

logger = get_logger()
settings = get_settings()


class Notifications:
    def __init__(self) -> None:
        """
        Initialize the Notifications system.

        Starts a background thread that processes the email notification queue

        Returns:
            None
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

        Parameters:
            to_emails (list): List of recipient email addresses.
            subject (str): The subject of the email.
            message (str): The body of the email.

        Returns:
            None
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

        Parameters:
            to_emails (list): List of recipient email addresses.
            subject (str): The subject of the email.
            message (str): The body of the email.

        Returns:
            None
        """

        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(settings.API_SMTP_HOST, settings.API_SMTP_PORT)
            server.starttls(context=context)
            server.login(settings.API_SMTP_USERNAME, settings.API_SMTP_PASSWORD)

            for email in to_emails:
                mail_to_send = f"From: Sunet Scribe <{settings.API_SMTP_SENDER}>\nTo: {email}\nSubject: {subject}\n\n{message}"
                server.sendmail(settings.API_SMTP_SENDER, to_emails, mail_to_send)
                logger.info(f"Email sent to {', '.join(to_emails)}")
        except Exception as e:
            logger.error(f"Error sending email to {", ".join(to_emails)}: {e}")

    def send_email_verification(self, to_email: str) -> None:
        """
        Send an email verification notification.

        Parameters:
            to_email (str): The recipient's email address.

        Returns:
            None
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

        Parameters:
            to_email (str): The recipient's email address.

        Returns:
            None
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

    def send_transcription_failed(self, to_email: str) -> None:
        """
        Send a transcription failed notification.

        Parameters:
            to_email (str): The recipient's email address.

        Returns:
            None
        """

        subject = "Your transcription job has failed"
        message = """\
        Hello,

        Unfortunately, your transcription job has failed.
        Please try again later or contact support if the problem persists.

        Best regards,
        Sunet Scribe Team
        """

        self.add(
            to_emails=[to_email],
            subject=subject,
            message=message,
        )

    def send_job_deleted(self, to_email: str) -> None:
        """
        Send a job deleted notification.

        Parameters:
            to_email (str): The recipient's email address.

        Returns:
            None
        """

        subject = "Your transcription job has been deleted"
        message = """\
        Hello,

        One of your transcription job has been deleted from Sunet Scribe since it was
        older than 7 days. Sunet Scribe don't keep transcription jobs for more than 7
        days for security and storage reasons.

        Best regards,
        Sunet Scribe Team
        """

        self.add(
            to_emails=[to_email],
            subject=subject,
            message=message,
        )

    def send_job_to_be_deleted(self, to_email: str) -> None:
        """
        Send a job to be deleted notification.

        Parameters:
            to_email (str): The recipient's email address.

        Returns:
            None
        """

        subject = "Your transcription job will be deleted soon"
        message = """\
        Hello,

        One of your transcription job will be deleted from Sunet Scribe in 24 hours since it
        is older than 7 days. Sunet Scribe don't keep transcription jobs for more than 7
        days for security and storage reasons.

        Best regards,
        Sunet Scribe Team
        """

        self.add(
            to_emails=[to_email],
            subject=subject,
            message=message,
        )


notifications = Notifications()


def notification_sent_record_add(
    user_id: str, uuid: str, notification_type: str
) -> None:
    """
    Record that a notification has been sent to avoid duplicates.

    Parameters:
        user_id (str): The ID of the user.
        uuid (str): The UUID of the job or entity.
        notification_type (str): The type of notification sent.

    Returns:
        None
    """

    with get_session() as session:
        notification = NotificationsSent(
            user_id=user_id,
            uuid=uuid,
            notification_type=notification_type,
        )
        session.add(notification)
        session.commit()


def notification_sent_record_exists(
    user_id: str, uuid: str, notification_type: str
) -> bool:
    """
    Check if a notification has already been sent.

    Parameters:
        user_id (str): The ID of the user.
        uuid (str): The UUID of the job or entity.
        notification_type (str): The type of notification sent.

    Returns:
        bool: True if the notification has been sent, False otherwise.
    """

    with get_session() as session:
        record = (
            session.query(NotificationsSent)
            .filter_by(
                user_id=user_id,
                uuid=uuid,
                notification_type=notification_type,
            )
            .first()
        )

        return record is not None
