import os
import uuid
from typing import List

from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse

from .core.config import *

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

STORAGE_BASE_URL = os.environ.get("STORAGE_BASE_URL")

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

async def upload_files(files: List[UploadFile]):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    uploaded_urls = {}

    for file in files:
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension == "mp3":
            folder = "music/"
        elif file_extension in ["jpg", "jpeg", "png"]:
            folder = "images/"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_extension}")

        # Генерация уникального имени файла
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = f"{folder}{unique_filename}"

        try:
            s3.upload_fileobj(file.file, BUCKET_NAME, file_path)

            full_url = STORAGE_BASE_URL + file_path

            if folder == "music/":
                uploaded_urls["track_url"] = full_url
            else:
                uploaded_urls["cover_url"] = full_url

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return uploaded_urls

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
