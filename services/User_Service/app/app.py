import typing, logging
from fastapi import FastAPI, Depends, Security, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from . import database, config, schemas, group_crud
from .auth import AuthInitializer, include_routers
import json
from fastapi.middleware.cors import CORSMiddleware

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/jwt/login")

# Initialize logger
logger = logging.getLogger("user-service")
logging.basicConfig(
    level=20,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger.info("Configuration loading...")
cfg: config.Config = config.load_config()
logger.info(
    'Service configuration loaded:\n' +
    f'{cfg.model_dump_json(by_alias=True, indent=4)}'
)

app = FastAPI(
    version='0.0.1',
    title='User service'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth = AuthInitializer()
auth.initializer(cfg.jwt_secret)

include_routers(app, auth.get_auth_backend(), auth.get_fastapi_users())

@app.on_event("startup")
async def on_startup():
    await database.db_initializer.init_db(
        str(cfg.PG_ASYNC_DSN)
    )

    groups = []
    with open(cfg.default_groups_config_path) as f:
        groups = json.load(f)

    if groups is not None:
        async for session in database.get_async_session():
            for group in groups:
                await group_crud.upsert_group(
                    session, schemas.GroupUpsert(**group)
                )
    else:
        logger.error('Конфигурация с группами не была загружена')

@app.post(
    "/groups", status_code=201, response_model=schemas.GroupRead,
    summary='Создает новую группу',
    tags=['groups']
)
async def add_group(
        group: schemas.GroupCreate,
        session: AsyncSession = Depends(database.get_async_session)
):
    return await group_crud.create_group(group, session)


@app.get(
    "/groups",
    summary='Возвращает список групп',
    response_model=list[schemas.GroupRead],
    tags=['groups']
)
async def get_groups(
        session: AsyncSession = Depends(database.get_async_session),
        skip: int = 0,
        limit: int = 100
) -> typing.List[schemas.GroupRead]:
    return await group_crud.get_groups(session, skip, limit)


@app.get(
    "/groups/{group_id}",
    summary='Возвращает информацию о группе',
    tags=['groups']
)
async def get_group(
        group_id: int, session: AsyncSession = Depends(database.get_async_session)
) -> schemas.GroupRead:
    group = await group_crud.get_group(session, group_id)
    if group != None:
        return group
    return JSONResponse(status_code=404, content={"message": "Item not found"})


@app.put(
    "/groups/{group_id}",
    summary='Обновляет информацию о группе',
    tags=['groups']
)
async def update_group(
        group_id: int,
        group: schemas.GroupUpdate,
        session: AsyncSession = Depends(database.get_async_session)
) -> schemas.GroupRead:
    group = await group_crud.update_group(session, group_id, group)
    if group != None:
        return group
    return JSONResponse(status_code=404, content={"message": "Item not found"})


@app.delete(
    "/groups/{group_id}",
    summary='Удаляет информацию о группе',
    tags=['groups']
)
async def delete_group(
        group_id: int,
        session: AsyncSession = Depends(database.get_async_session)
) -> schemas.GroupRead:
    if await group_crud.delete_group(session, group_id):
        return JSONResponse(status_code=200, content={"message": "Item successfully deleted"})
    return JSONResponse(status_code=404, content={"message": "Item not found"})


@app.get("/protected-test", tags=["auth"])
async def protected_route(token: str = Security(oauth2_scheme)):
    return {"message": "Вы авторизованы!", "token": token}