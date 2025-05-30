import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import List

from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse

from .core.config import *

from mutagen.mp3 import MP3
from tempfile import NamedTemporaryFile

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

STORAGE_BASE_URL = os.environ.get("STORAGE_BASE_URL")

# async def list_files():
#     try:
#         async with get_s3_client() as s3:
#             response = await s3.list_objects_v2(Bucket=BUCKET_NAME)
#             if "Contents" in response:
#                 return [obj["Key"] for obj in response["Contents"]]
#             return []
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
# async def generate_presigned_url(file_path: str) -> str:
#     try:
#         async with get_s3_client() as s3:
#             return await s3.generate_presigned_url(
#                 ClientMethod='get_object',
#                 Params={'Bucket': BUCKET_NAME, 'Key': file_path},
#                 ExpiresIn=60000
#             )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
# async def download_file(file_path: str):
#     try:
#         async with get_s3_client() as s3:
#             response = await s3.get_object(Bucket=BUCKET_NAME, Key=file_path)
#             body = await response["Body"].read()
#
#             temp_file_path = f"/tmp/{os.path.basename(file_path)}"
#             with open(temp_file_path, "wb") as f:
#                 f.write(body)
#
#             return FileResponse(temp_file_path, filename=os.path.basename(file_path))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
# async def delete_file(file_path: str):
#     try:
#         async with get_s3_client() as s3:
#             await s3.delete_object(Bucket=BUCKET_NAME, Key=file_path)
#         return {"message": f"The file {file_path} has been deleted successfully"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

def list_files():
    try:
        response = s3.list_objects(Bucket=BUCKET_NAME)
        if "Contents" in response:
            return [obj["Key"] for obj in response["Contents"]]
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_presigned_url(file_path: str) -> str:
    try:
        return s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': file_path},
            ExpiresIn=60000
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

executor = ThreadPoolExecutor(max_workers=40)

def upload_file_sync(content: bytes, filename: str) -> tuple[str, str]:
    ext = filename.split('.')[-1].lower()
    if ext == "mp3":
        folder = "music/"
        key = "track_url"
    elif ext in ["jpg", "jpeg", "png"]:
        folder = "images/"
        key = "cover_url"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    unique_filename = f"{uuid.uuid4()}.{ext}"
    file_path = f"{folder}{unique_filename}"

    with NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        s3.upload_file(temp_path, BUCKET_NAME, file_path)
    finally:
        os.remove(temp_path)

    return key, STORAGE_BASE_URL + file_path

async def upload_files(files: list[UploadFile]) -> dict[str, str]:
    loop = asyncio.get_event_loop()
    file_data = []
    for file in files:
        content = await file.read()
        file_data.append((content, file.filename))
        file.file.seek(0)

    tasks = [loop.run_in_executor(executor, upload_file_sync, content, filename)
             for content, filename in file_data]
    results = await asyncio.gather(*tasks)
    return {k: v for k, v in results}

async def extract_duration(file: UploadFile) -> float:
    content = await file.read()
    audio = MP3(BytesIO(content))
    file.file.seek(0)
    return audio.info.length

# async def upload_files(file: UploadFile) -> tuple[str, str]:
#     ext = file.filename.split('.')[-1].lower()
#     if ext == "mp3":
#         folder = "music/"
#         key = "track_url"
#     elif ext in ["jpg", "jpeg", "png"]:
#         folder = "images/"
#         key = "cover_url"
#     else:
#         raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
#
#     unique_filename = f"{uuid.uuid4()}.{ext}"
#     file_path = f"{folder}{unique_filename}"
#
#     try:
#         await file.seek(0)  # ensure we’re at the start
#         s3.upload_fileobj(file.file, BUCKET_NAME, file_path)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#
#     return key, STORAGE_BASE_URL + file_path

# async def upload_files(files: List[UploadFile]):
#     if not files:
#         raise HTTPException(status_code=400, detail="No files provided")
#
#     uploaded_urls = {}
#
#     for file in files:
#         file_extension = file.filename.split('.')[-1].lower()
#         if file_extension == "mp3":
#             folder = "music/"
#         elif file_extension in ["jpg", "jpeg", "png"]:
#             folder = "images/"
#         else:
#             raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_extension}")
#
#         # Генерация уникального имени файла
#         unique_filename = f"{uuid.uuid4()}.{file_extension}"
#         file_path = f"{folder}{unique_filename}"
#
#         try:
#             s3.upload_fileobj(file.file, BUCKET_NAME, file_path)
#
#             full_url = STORAGE_BASE_URL + file_path
#
#             if folder == "music/":
#                 uploaded_urls["track_url"] = full_url
#             else:
#                 uploaded_urls["cover_url"] = full_url
#
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=str(e))
#
#     return uploaded_urls

def download_file(file_path: str):
    try:
        file_object = s3.get_object(Bucket=BUCKET_NAME, Key=file_path)
        temp_file_path = f"/tmp/{os.path.basename(file_path)}"

        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file_object["Body"].read())

        return FileResponse(temp_file_path, filename=os.path.basename(file_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def delete_file(file_path: str):
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=file_path)
        return {"message": f"The file {file_path} has been deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
