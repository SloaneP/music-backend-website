import uuid
from typing import Optional
from fastapi_users import schemas
from pydantic import Field

class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str | None = None
    group_id: int | None = None


class UserCreate(schemas.BaseUserCreate):
    username: str = None
    group_id: int = None


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    password: Optional[str] = None
    # group_id: Optional[int] = None
