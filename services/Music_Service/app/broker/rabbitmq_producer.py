from datetime import datetime

import aio_pika
import json
from uuid import UUID
from ..config import load_config

cfg = load_config()
RABBITMQ_DSN = cfg.RABBITMQ_DSN

def prepare_event_data(data: dict) -> dict:
    clean_data = {}
    for k, v in data.items():
        if isinstance(v, UUID):
            clean_data[k] = str(v)
        elif isinstance(v, datetime):
            clean_data[k] = v.isoformat()
        else:
            clean_data[k] = v
    return clean_data

async def send_track_play_event(event_data: dict):
    connection = await aio_pika.connect_robust(str(cfg.RABBITMQ_DSN))
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("track_events", aio_pika.ExchangeType.FANOUT, durable=True)

        clean_data = prepare_event_data(event_data)

        message = aio_pika.Message(
            body=json.dumps(clean_data).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        await exchange.publish(message, routing_key="")
