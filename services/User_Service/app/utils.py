from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .database import models

from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Union, Any
from jose import jwt

import logging

import time

from . import schemas


class HashContext():
    def __init__(
            self,
            JWT_SECRET_KEY: str,
            JWT_REFRESH_SECRET_KEY: str,
            ACCESS_TOKEN_EXPIRE_MINUTES=60,  # 60 minutes
            REFRESH_TOKEN_EXPIRE_MINUTES=60 * 24 * 7,  # 7 days
            ALGORITHM="HS256",
    ):
        self.JWT_SECRET_KEY = JWT_SECRET_KEY
        self.JWT_REFRESH_SECRET_KEY = JWT_REFRESH_SECRET_KEY
        self.ACCESS_TOKEN_EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_MINUTES = REFRESH_TOKEN_EXPIRE_MINUTES
        self.ALGORITHM = ALGORITHM
        self.denylist = set()

        self.password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def get_hashed_password(self, password: str) -> str:
        return self.password_context.hash(password)

    def add_token_to_deny_list(self, token: str):
        self.denylist.add(token)

    def is_token_in_deny_list(self, token: str):
        return token in self.denylist

    def verify_password(self, password: str, hashed_pass: str) -> bool:
        return self.password_context.verify(password, hashed_pass)

    def decode_token(self, token: str, key: str, algorithm: str) -> dict | None:
        if self.is_token_in_deny_list(token):
            return None

        try:
            decoded_token = jwt.decode(token, key, algorithms=[algorithm])
            return decoded_token if decoded_token["exp"] >= time.time() else None
        except Exception as e:
            logging.error(e)
            return None

    def create_access_token(self, subject: models.User, expires_delta: int = None) -> str:
        if expires_delta is not None:
            expires_delta = datetime.utcnow() + expires_delta
        else:
            expires_delta = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode = schemas.TokenPayload(
            sub=str(subject.email),
            exp=int(expires_delta.timestamp()),
            group_id=subject.group_id,
        ).model_dump()

        encoded_jwt = jwt.encode(to_encode, self.JWT_SECRET_KEY, self.ALGORITHM)
        return encoded_jwt

    def decode_access_token(self, token: str) -> dict:
        decoded_token = jwt.decode(token, self.JWT_SECRET_KEY, self.ALGORITHM)
        return decoded_token

    def verify_access_token(self, token: str) -> bool:
        if self.decode_access_token(token): return True
        return False

    def create_refresh_token(self, subject: models.User, expires_delta: int = None) -> str:
        if expires_delta is not None:
            expires_delta = datetime.utcnow() + expires_delta
        else:
            expires_delta = datetime.utcnow() + timedelta(minutes=self.REFRESH_TOKEN_EXPIRE_MINUTES)

        to_encode = schemas.TokenPayload(
            sub=str(subject.email),
            exp=int(expires_delta.timestamp()),
            group_id=subject.group_id,
        ).model_dump()

        encoded_jwt = jwt.encode(to_encode, self.JWT_REFRESH_SECRET_KEY, self.ALGORITHM)
        return encoded_jwt

    def decode_refresh_token(self, token: str) -> dict:
        return self.decode_token(token, self.JWT_REFRESH_SECRET_KEY, self.ALGORITHM)

    def verify_refresh_token(self, token: str) -> bool:
        if self.decode_refresh_token(token): return True
        return False


class JWTBearer(HTTPBearer):
    def __init__(self, hash_context: HashContext, auto_error: bool = True):
        self.hash_context = hash_context
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    def verify_jwt(self, jwtoken: str) -> bool:
        return self.hash_context.verify_access_token(jwtoken)