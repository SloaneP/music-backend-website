import logging
import re
import tempfile

import casbin
import jwt
import yaml
from fastapi import Request
from pydantic.dataclasses import dataclass

from .config import PoliciesConfig, Policy, Service

logger = logging.getLogger("policy-enforcement-service")

@dataclass
class EnforceResult:
    access_allowed: bool = False
    redirect_service: str | None = None


class RequestEnforcer:
    def __init__(self, config_path: str, jwt_secret: str) -> None:
        self.jwt_secret: str = jwt_secret
        self.config: PoliciesConfig = self.__load_config(config_path=config_path)
        self.enforcer: casbin.Enforcer = self.__create_enforcer()

    async def enforce(self, request: Request) -> EnforceResult:
        in_whitelist, service_name = self.__is_request_in_whilelist(request)
        if in_whitelist:
            service = self.__get_service_by_name(service_name)
            return EnforceResult(True, str(service.entrypoint))

        access_allowed, service_name = await self.__check_by_policy(request)
        if access_allowed:
            service = self.__get_service_by_name(service_name)
            return EnforceResult(True, str(service.entrypoint))

        logger.info(f"Checking whitelist for service: {service_name}")
        return EnforceResult()

    def __load_config(self, config_path: str) -> PoliciesConfig:
        with open(config_path) as file:
            data = yaml.safe_load(file)
            return PoliciesConfig(**data)

    def __create_enforcer(self) -> casbin.Enforcer:
        model_conf = self.__make_model_temp_file()
        policy_conf = self.__make_policy_temp_file()
        return casbin.Enforcer(model_conf, policy_conf)

    def __make_model_temp_file(self) -> str:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        with open(tmp.name, 'w') as f:
            f.write(self.config.model)

        return tmp.name

    def __make_policy_temp_file(self) -> str:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        with open(tmp.name, 'w') as f:
            f.writelines(
                list(f'p, {p.rule}, {p.resource}, {p.methods}\n' for p in self.config.policies if not p.white_list)
            )
        return tmp.name

    def __extract_token_data(self, request: Request) -> dict:
        try:
            # Проверяем, есть ли в заголовке авторизация
            if 'authorization' in request.headers:
                token = request.headers['authorization'].split(' ')[1]  # Извлекаем токен из заголовка
                # Декодируем токен и извлекаем данные
                return jwt.decode(token, self.jwt_secret, algorithms=["HS256"], audience=["fastapi-users:auth"])

            # Если токена нет, возвращаем group_id = 0 для неавторизованного пользователя
            return {"group_id": 0}

        except Exception as e:
            # В случае ошибки (например, токен поврежден) также возвращаем group_id = 0
            logger.error(f"Error extracting token: {e}")
            return {"group_id": 0}

    # def __extract_token_data(self, request: Request) -> dict:
    #     try:
    #         if 'authorization' in request.headers:
    #             token = request.headers['authorization'].split(' ')[1]
    #             return jwt.decode(token, self.jwt_secret, algorithms=["HS256"], audience=["fastapi-users:auth"])
    #     except:
    #         return None
    #     return None

    def __is_request_in_whilelist(self, request: Request) -> tuple[bool, str]:
        resource = '/' + request.path_params['path_name']
        for p in self.whilelist_policies:
            if re.match(p.resource, resource) is not None and request.method in p.method_list:
                return True, p.service
        return False, None

    async def __check_by_policy(self, request: Request) -> tuple[bool, str]:
        # Получаем ресурс из пути запроса
        resource = '/' + request.path_params['path_name']

        # Извлекаем данные о пользователе (если есть токен, получим его данные, если нет — назначим group_id = 0)
        token_data = self.__extract_token_data(request)
        group_id = token_data.get("group_id", 0)  # Присваиваем group_id по умолчанию, если токена нет

        # Проверяем доступ по политике с casbin
        access_allowed = self.enforcer.enforce({"group_id": group_id}, resource, request.method)
        if not access_allowed:
            return False, None

        # Если доступ разрешён, находим сервис
        for p in self.enforcing_policies:
            if re.match(p.resource, resource) is not None and request.method in p.method_list:
                return True, p.service

        return True, None

    # async def __check_by_policy(self, request: Request) -> tuple[bool, str]:
    #     token_data = self.__extract_token_data(request)
    #
    #     if token_data is None:
    #         return False, None
    #
    #     resource = '/' + request.path_params['path_name']
    #
    #     access_allowed = self.enforcer.enforce(token_data, resource, request.method)
    #     if access_allowed is False:
    #         return False, None
    #
    #     for p in self.enforcing_policies:
    #         if re.match(p.resource, resource) is not None and request.method in p.method_list:
    #             return True, p.service
    #
    #     return True, None

    def __get_service_by_name(self, service_name: str) -> Service:
        logger.info(f"Checking whitelist for service: {service_name}")
        for s in self.config.services:
            if s.name == service_name:
                return s
        return None

    @property
    def service_schemes(self) -> list[str]:
        return [s.openapi_scheme for s in self.config.services]

    @property
    def services(self) -> list[Service]:
        return [s for s in self.config.services]

    @property
    def whilelist_resources(self) -> list[str]:
        return [p.resource for p in self.config.policies if p.white_list]

    @property
    def whilelist_policies(self) -> list[Policy]:
        return [p for p in self.config.policies if p.white_list]

    @property
    def enforcing_policies(self) -> list[Policy]:
        return [p for p in self.config.policies if not p.white_list]