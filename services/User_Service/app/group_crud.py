import typing

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .database import models
from . import schemas


async def create_group(group: schemas.GroupCreate, session: AsyncSession) -> models.Group:
    '''
    Create a new user group
    '''
    db_group = models.Group(name=group.name)
    session.add(db_group)
    await session.commit()
    await session.refresh(db_group)
    return db_group


async def get_groups(session: AsyncSession, skip: int = 0, limit: int = 100) -> typing.List[models.Group]:
    '''
    Get all user groups
    '''
    query = select(models.Group).offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


async def get_group(session: AsyncSession, group_id: int) -> models.Group:
    '''
    Get a user group by ID
    '''
    query = select(models.Group).filter(models.Group.id == group_id).limit(1)
    result = await session.execute(query)
    return result.scalars().one_or_none()


async def update_group(session: AsyncSession, group_id: int, group: schemas.GroupUpdate) -> models.Group:
    '''
    Update a user group by ID
    '''
    query = update(models.Group).where(models.Group.id == group_id).values(group.model_dump())
    result = await session.execute(query)
    await session.commit()

    if result:
        return await get_group(session, group_id)
    return None

async def upsert_group(
    session: AsyncSession, group: schemas.GroupUpsert
) -> models.Group:
    '''
    Обновляет или добавляет группу пользователей в базу
    '''

    stm = insert(models.Group).values(group.model_dump())
    stm = stm.on_conflict_do_update(
        constraint='group_pkey',
        set_={"name": group.name}
    )
    result = await session.execute(stm)

    await session.commit()
    if result:
        return await get_group(session, group.id)
    return None

async def delete_group(session: AsyncSession, group_id: int) -> bool:
    '''
    Remove a user group by ID
    '''
    has_group = await get_group(session, group_id)
    query = delete(models.Group).filter(models.Group.id == group_id)
    await session.execute(query)
    await session.commit()

    return bool(has_group)