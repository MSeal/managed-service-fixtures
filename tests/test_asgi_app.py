from typing import Callable

import httpx
import pytest
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from managed_service_fixtures import AppDetails
from managed_service_fixtures.services.asgi_app import AppManager

app = FastAPI()


@app.get("/")
async def index():
    return {"Hello": "World"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            msg = await websocket.receive_text()
            await websocket.send_text(f"echo: {msg}")
        except WebSocketDisconnect:
            break


@pytest.fixture(scope="session")
def fastapi_app(managed_asgi_app_factory: Callable[[str], AppManager]) -> AppDetails:
    app_location = "tests.test_asgi_app:app"
    with managed_asgi_app_factory(app_location) as app_details:
        yield app_details


async def test_get(fastapi_app: AppDetails):
    async with httpx.AsyncClient(base_url=fastapi_app.url) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"Hello": "World"}


async def test_ws(fastapi_app: AppDetails):
    async with websockets.connect(fastapi_app.ws_base + "/ws") as websocket:
        await websocket.send("Hello")
        resp = await websocket.recv()
        assert resp == "echo: Hello"
        await websocket.close()
