import uuid

from fastapi_users import schemas

class UserRead(schemas.BaseUser[uuid.UUID]):
    username: str | None = None
    group_id: int | None = None


class UserCreate(schemas.BaseUserCreate):
    username: str = None
    group_id: int = None


class UserUpdate(schemas.BaseUserUpdate):
    username: str = None
    group_id: int | None = None