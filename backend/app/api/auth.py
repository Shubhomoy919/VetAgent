"""Access code: unlock (sets the session cookie), lock (clears it), and who-am-I."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.security import check_code, clear_session_cookie, client_ip, is_admin, lockout, set_session_cookie

router = APIRouter(prefix="/api/auth")


class Unlock(BaseModel):
    code: str = Field(min_length=1, max_length=256)


def _status(request: Request, settings: Settings) -> dict:
    return {
        "admin": is_admin(request, settings),
        "access_required": settings.access_required,
        # False when production has no ADMIN_ACCESS_CODE: the site is permanently read-only.
        "unlock_available": bool(settings.admin_access_code.strip()),
        "locked_for_s": lockout.locked_for(client_ip(request), settings),
    }


@router.get("/status")
def status(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    return _status(request, settings)


@router.post("/unlock")
def unlock(body: Unlock, request: Request, settings: Settings = Depends(get_settings)) -> JSONResponse:
    ip = client_ip(request)
    if not settings.admin_access_code.strip():
        return JSONResponse(status_code=403, content={"detail": "This deployment is read-only: no access code is configured."})
    wait = lockout.locked_for(ip, settings)
    if wait:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many wrong codes. Try again in {max(1, wait // 60)} min.", "locked_for_s": wait},
            headers={"Retry-After": str(wait)},
        )
    if not check_code(body.code, settings):
        left = lockout.fail(ip, settings)
        if left <= 0:
            wait = lockout.locked_for(ip, settings)
            return JSONResponse(
                status_code=429,
                content={"detail": f"Too many wrong codes. Try again in {max(1, wait // 60)} min.", "locked_for_s": wait},
                headers={"Retry-After": str(wait)},
            )
        return JSONResponse(status_code=401, content={"detail": f"Wrong access code. {left} attempt{'s' if left != 1 else ''} left.", "attempts_left": left})
    lockout.succeed(ip)
    response = JSONResponse(content={"admin": True})
    set_session_cookie(response, settings)
    return response


@router.post("/lock")
def lock(settings: Settings = Depends(get_settings)) -> JSONResponse:
    response = JSONResponse(content={"admin": False})
    clear_session_cookie(response, settings)
    return response
