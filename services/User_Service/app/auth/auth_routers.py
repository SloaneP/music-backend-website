import uuid
from fastapi import FastAPI
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend
from ..schemas import schemas

def include_routers(app: FastAPI, auth_backend: AuthenticationBackend, fastapi_users: FastAPIUsers):
    app.include_router(
        fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_register_router(schemas.UserRead, schemas.UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(schemas.UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(schemas.UserRead, schemas.UserUpdate),
        prefix="/users",
        tags=["users"],
    )