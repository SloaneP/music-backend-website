import logging
from uuid import UUID
from typing import Optional
import jwt
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from . import crud
from .database import db_initializer, get_async_session
from .config import load_config

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

app = FastAPI(
    title=cfg.SERVICE_NAME,
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    try:
        await db_initializer.init_db(str(cfg.PG_ASYNC_DSN))
        logger.info("Database initialized successfully.")
        logger.info(f"Async session maker: {db_initializer.async_session_maker}")
    except Exception as e:
        logger.exception("Failed to initialize database: %s", e)


# ─────────── TOKEN ─────────── #
def extract_email_data(token: str) -> Optional[tuple[str, UUID]]:
    logger.info(f"Decoding token: {token}")
    try:
        data = jwt.decode(
            token,
            cfg.JWT_SECRET,
            algorithms=["HS256"],
            audience=["fastapi-users:auth"]
        )
        logger.info(f"Token decoded successfully: {data}")

        email = data.get("email")
        user_id = data.get("sub")

        logger.info(f"Extracted email: {email}, user_id: {user_id}")
        if email and user_id:
            return email, UUID(user_id)

    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while decoding token: {e}")

    logger.warning("Returning None from extract_email_data")
    return None

async def get_current_user(request: Request) -> tuple[str, UUID] | None:
    auth_header = request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    user_data = extract_email_data(token)

    if not user_data:
        logger.warning("Invalid or expired token")
        return None

    email, user_id = user_data
    return email, user_id

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# ─────────── FETCH DATA FROM MUSIC_SERVICE ROUTES ─────────── #
@app.get("/user/analytics/raw-data")
async def get_raw_data(
    request: Request,
    user_id: UUID | None = Query(None),
    internal: bool = Query(False),
    db: AsyncSession = Depends(get_async_session)
):
    token = None
    if not internal:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        token = auth_header.split(" ")[1]
        user_data = extract_email_data(token)
        if not user_data:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        _, user_id = user_data
    else:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required for internal call")

    result = await crud.get_and_update_user_analytics(db, user_id, token=token, internal_call=internal)
    return result
