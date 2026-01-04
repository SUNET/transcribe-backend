from fastapi import HTTPException, Request
from typing import Optional
from utils.log import get_logger
from utils.settings import get_settings

settings = get_settings()
log = get_logger()

dn_list = [settings.API_WORKER_CLIENT_DN, settings.API_KALTURA_CLIENT_DN]


def verify_client_dn(
    request: Request,
) -> Optional[str]:
    """
    Verify the client DN from the request headers.
    """

    client_dn = request.headers.get(settings.API_CLIENT_VERIFICATION_HEADER, "")

    if settings.API_CLIENT_VERIFICATION_ENABLED is False:
        return "bypass-client-cert"

    if client_dn.strip() not in dn_list:
        log.info(f"Client failed to authenticate with {client_dn}")
        raise HTTPException(status_code=403, detail="Invalid request")

    log.info(f"Client authenticated with {client_dn}")

    return client_dn


def dn_in_list(dn):
    """
    Check if the given DN is in the allowed DN list.
    """

    # Bypass check if verification is disabled
    if settings.API_CLIENT_VERIFICATION_ENABLED is False:
        return True

    accept = dn in dn_list

    log.info(f"DN {dn} acceptance: {accept}")

    return accept
