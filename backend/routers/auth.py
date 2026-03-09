"""POST /api/auth — exchange an invite code for a JWT."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tools.auth import create_token
from tools.invite import consume_invite_code
from tools.limiter import limiter

router = APIRouter()


class AuthRequest(BaseModel):
    code: str


@router.post("/auth")
@limiter.limit("5/15minute")
async def auth(request: Request, body: AuthRequest):
    valid = await consume_invite_code(body.code)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid invite code.")
    token = create_token()
    return {"valid": True, "token": token}
