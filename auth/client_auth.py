
from fastapi import  Request, HTTPException
from utils.settings import get_settings
from typing import Optional

settings = get_settings()

def verify_client_dn(
    request: Request,
) -> Optional[str]:
    """
    Verify the client DN from the request headers.
    """

    DN_list = [settings.API_WORKER_CLIENT_DN, settings.API_KALTURA_CLIENT_DN]

    client_dn = request.headers.get("x-client-dn")

    if settings.API_CLIENT_VERIFICATION_ENABLED is False:
        return client_dn

    if not client_dn or client_dn.strip() not in  DN_list:
        raise HTTPException(status_code=403, detail="Invalid request")

    return client_dn
