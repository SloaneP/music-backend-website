import os
from pathlib import Path

import boto3
from dotenv import load_dotenv
import aioboto3
from botocore.config import Config

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

BUCKET_NAME = os.environ.get("BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

session = boto3.session.Session()
# session = aioboto3.Session()

s3 = session.client(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    service_name="s3",
    endpoint_url="https://storage.yandexcloud.net",
    config=Config(
        retries={"max_attempts": 3, "mode": "standard"},
        max_pool_connections=50,
        connect_timeout=5,
        read_timeout=30,
    )
)

# def get_s3_client():
#     return session.client(
#         service_name="s3",
#         aws_access_key_id=AWS_ACCESS_KEY_ID,
#         aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
#         endpoint_url="https://storage.yandexcloud.net",
#     )