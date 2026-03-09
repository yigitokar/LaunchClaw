from fastapi import Header, HTTPException

from app.db import get_supabase


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """Extract and verify the user from the Supabase JWT in the Authorization header."""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

    supabase = get_supabase()
    resp = supabase.auth.get_user(token)

    if resp is None or resp.user is None:
        raise HTTPException(status_code=401, detail="unauthorized")

    return resp.user.id
