"""POST /api/auth — exchange an invite code for a JWT."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tools.auth import create_token
from tools.invite import consume_invite_code
from tools.limiter import limiter
from tools.rate_limit import check_auth_lockout, record_auth_failure, record_auth_success

router = APIRouter()


class AuthRequest(BaseModel):
    code: str


@router.post("/auth")
@limiter.limit("10/minute")
async def auth(request: Request, body: AuthRequest):
    ip = request.client.host if request.client else "unknown"

    allowed, lockout_msg = check_auth_lockout(ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=lockout_msg)

    valid = await consume_invite_code(body.code)
    if not valid:
        record_auth_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid invite code.")

    record_auth_success(ip)
    token = create_token()
    return {"valid": True, "token": token}
