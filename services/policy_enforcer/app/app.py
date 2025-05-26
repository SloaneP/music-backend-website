import logging
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .policies.enforcer import EnforceResult, RequestEnforcer
from .scheme_builder import SchemeBuilder

# setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s][%(name)s][%(filename)s, line %(lineno)d]: %(message)s"
)

app_config: config.Config = config.load_config(_env_file='.env')

policy_checker: RequestEnforcer = RequestEnforcer(
    app_config.policies_config_path, app_config.jwt_secret.get_secret_value()
)
logger.info(f"Policy services loaded: {policy_checker.services}")


class App(FastAPI):
    def openapi(self) -> Dict[str, Any]:
        scheme_builder = SchemeBuilder(super().openapi())

        for target in policy_checker.services:
            resp = httpx.get(target.openapi_scheme)
            scheme_builder.append(resp.json(), inject_token_in_swagger=target.inject_token_in_swagger)
        return scheme_builder.result


app = App()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5001",
    "http://localhost:5002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.api_route("/{path_name:path}",
               methods=["GET", "DELETE", "PATCH", "POST", "PUT", "HEAD", "OPTIONS", "CONNECT", "TRACE"],
               operation_id="catch_all_operation")
async def catch_all(request: Request, path_name: str):
    if path_name == "":
        return RedirectResponse(url='/docs')

    enforce_result: EnforceResult = await policy_checker.enforce(request)
    if not enforce_result.access_allowed:
        return JSONResponse(content={'message': 'Content not found'}, status_code=404)

    # client = httpx.AsyncClient(base_url=enforce_result.redirect_service)
    client = httpx.AsyncClient(
        base_url=enforce_result.redirect_service,
        timeout=httpx.Timeout(20.0)
    )
    url = httpx.URL(path=request.url.path,
                    query=request.url.query.encode("utf-8"))
    rp_req = client.build_request(request.method, url,
                                  headers=dict(request.headers),
                                  content=await request.body())
    rp_resp = await client.send(rp_req, stream=True)

    return StreamingResponse(
        rp_resp.aiter_raw(),
        status_code=rp_resp.status_code,
        headers=rp_resp.headers
    )