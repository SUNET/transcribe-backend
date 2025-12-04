import smtplib
import ssl
import collections
import threading 

from utils.settings import get_settings
from utils.log import get_logger


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

                self.__notification_send_email(
                    to_emails=notification["to_emails"],
                    from_email=notification["from_email"],
                    subject=notification["subject"],
                    message=notification["message"],
                )

        handler()

    def __add(self, to_emails: list, from_email: str, subject: str, message: str) -> None:
        """
        Queue an email notification to be sent later.
        """

        if not settings.API_SMTP_HOST:
            logger.warning("SMTP host is not configured. Email notifications will not be sent.")
            return

        self.__queue.append(
            {
                "to_emails": to_emails,
                "from_email": from_email,
                "subject": subject,
                "message": message,
            }
        )

    def __notification_send_email(self, to_emails: list, from_email: str, subject: str, message: str) -> None:
        """
        Send an email notification.
        """

        context = ssl.create_default_context()
        mail_to_send = f"""\
        Subject: {subject}
        {message}
        """

        try:
            server = smtplib.SMTP(settings.API_SMTP_HOST, settings.API_SMTP_PORT)
            server.starttls(context=context)
            server.login(settings.API_SMTP_USER, settings.API_SMTP_PASSWORD)
            server.sendmail(from_email, to_emails, mail_to_send)
        except Exception as e:
            logger.error(f"Error sending email to {", ".join(to_emails)}: {e}")

notifications = Notifications()


def notification_new_user(username: str) -> None:
    """
    Notify admin of a new user registration.
    """

    subject = "New user waiting for approval"
    message = f"A new user has registered with the username: {username}"
    notifications._Notifications__add(
        to_emails=[settings.API_SMTP_SENDER],
        from_email=settings.API_SMTP_SENDER,
        subject=subject,
        message=message,
    )


if __name__ == "__main__":
    notification_new_user("testuser0")
    notification_new_user("testuser1")
    notification_new_user("testuser2")
    notification_new_user("testuser3")
    notification_new_user("testuser4")                