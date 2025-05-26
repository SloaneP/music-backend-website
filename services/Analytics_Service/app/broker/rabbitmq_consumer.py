import aio_pika
import asyncio
import json
from uuid import UUID
from ..app import crud, schemas
from ..config import load_config
from ..database import get_async_session

cfg = load_config()

async def on_track_play_event(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            data = json.loads(message.body)
            user_id = UUID(data["user_id"])

            async for session in get_async_session():
                event_schema = schemas.TrackPlayEventCreate(
                    user_id=user_id,
                    track_id=UUID(data["track_id"]),
                    played_duration=data["played_duration"],
                    total_duration=data["total_duration"],
                    is_completed=data["is_completed"],
                    played_at=data.get("played_at"),
                    artist=data.get("artist"),
                    genre=data.get("genre"),
                    release_year=data.get("release_year"),
                )
                await crud.create_play_event(session, event_schema)
                await crud.aggregate_user_profile(session, user_id)
                await session.commit()
                await session.close()
                break
        except Exception as e:
            print(f"Error processing message: {e}")

async def consume_track_play_events():
    connection = await aio_pika.connect_robust(cfg.RABBITMQ_DSN)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("track_events", aio_pika.ExchangeType.FANOUT, durable=True)
        queue = await channel.declare_queue("", exclusive=True)
        await queue.bind(exchange, routing_key="")
        await queue.consume(on_track_play_event)
        print(" [*] Started consuming track_play_events...")

        # Удерживаем задачу в работе, пока не отменят
        try:
            await asyncio.Future()  # Блокируемся навсегда
        except asyncio.CancelledError:
            print("Consumer task cancelled, exiting")