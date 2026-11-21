"""Testovi funkcionalnosti, granica, validacije i autentikacije API-ja."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from pytest import MonkeyPatch
from starlette.types import Message, Receive, Scope, Send

from app.main import API_KEY_ENV, app

TEST_API_KEY = "test-api-key-with-enough-entropy"


@dataclass(frozen=True)
class ApiResponse:
    """Minimalni odgovor potreban za provjere u testovima."""

    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        """Dekodiraj JSON tijelo odgovora."""

        return json.loads(self.body)


async def send_asgi_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, int | float | bool] | None = None,
) -> ApiResponse:
    """Pošalji jedan HTTP zahtjev direktno FastAPI ASGI aplikaciji."""

    body = json.dumps(json_body).encode() if json_body is not None else b""
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    if json_body is not None:
        raw_headers.append((b"content-type", b"application/json"))

    request_available = True

    async def receive() -> Message:
        nonlocal request_available
        if request_available:
            request_available = False
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    receive_call: Receive = receive
    send_call: Send = send
    await app(scope, receive_call, send_call)

    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {key.decode(): value.decode() for key, value in start.get("headers", [])}
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return ApiResponse(
        status_code=start["status"],
        headers=response_headers,
        body=response_body,
    )


def request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, int | float | bool] | None = None,
) -> ApiResponse:
    """Pokreni ASGI zahtjev u zasebnoj asyncio petlji."""

    return asyncio.run(send_asgi_request(method, path, headers=headers, json_body=json_body))


@pytest.fixture(autouse=True)
def configured_api_key(monkeypatch: MonkeyPatch) -> None:
    """Postavi privremeni API ključ za svaki test."""

    monkeypatch.setenv(API_KEY_ENV, TEST_API_KEY)


def auth_headers() -> dict[str, str]:
    """Vrati validno autentifikaciono zaglavlje za testove."""

    return {"X-API-Key": TEST_API_KEY}


def test_health_endpoint_is_public() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_price_without_discount() -> None:
    response = request(
        "POST",
        "/cijena",
        headers=auth_headers(),
        json_body={"noci": 3, "cijena_noci": 80},
    )

    assert response.status_code == 200
    assert response.json() == {"iznos": "240.00", "valuta": "EUR"}


@pytest.mark.parametrize(
    ("payload", "expected_amount"),
    [
        ({"noci": 1, "cijena_noci": 100, "popust": 0}, "100.00"),
        ({"noci": 30, "cijena_noci": 10, "popust": 0}, "300.00"),
        ({"noci": 2, "cijena_noci": 50, "popust": 0.5}, "50.00"),
        ({"noci": 3, "cijena_noci": 80, "popust": 1}, "0.00"),
        ({"noci": 1, "cijena_noci": 10.01, "popust": 0.15}, "8.51"),
    ],
)
def test_price_valid_boundaries_and_rounding(
    payload: dict[str, int | float],
    expected_amount: str,
) -> None:
    response = request("POST", "/cijena", headers=auth_headers(), json_body=payload)

    assert response.status_code == 200
    assert response.json()["iznos"] == expected_amount


@pytest.mark.parametrize(
    "payload",
    [
        {"noci": 0, "cijena_noci": 80},
        {"noci": 31, "cijena_noci": 80},
        {"noci": -1, "cijena_noci": 80},
        {"noci": 2, "cijena_noci": 0},
        {"noci": 2, "cijena_noci": -10},
        {"noci": 2, "cijena_noci": 80, "popust": -0.01},
        {"noci": 2, "cijena_noci": 80, "popust": 1.01},
    ],
)
def test_invalid_numeric_input_returns_422(
    payload: dict[str, int | float],
) -> None:
    response = request("POST", "/cijena", headers=auth_headers(), json_body=payload)

    assert response.status_code == 422


def test_missing_required_field_returns_422() -> None:
    response = request(
        "POST",
        "/cijena",
        headers=auth_headers(),
        json_body={"noci": 2},
    )

    assert response.status_code == 422


def test_extra_field_is_rejected() -> None:
    response = request(
        "POST",
        "/cijena",
        headers=auth_headers(),
        json_body={"noci": 2, "cijena_noci": 80, "admin": True},
    )

    assert response.status_code == 422


def test_missing_api_key_returns_401() -> None:
    response = request("POST", "/cijena", json_body={"noci": 2, "cijena_noci": 80})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"


def test_wrong_api_key_returns_403() -> None:
    response = request(
        "POST",
        "/cijena",
        headers={"X-API-Key": "wrong-key"},
        json_body={"noci": 2, "cijena_noci": 80},
    )

    assert response.status_code == 403


def test_missing_server_configuration_returns_503(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ENV)

    response = request(
        "POST",
        "/cijena",
        headers=auth_headers(),
        json_body={"noci": 2, "cijena_noci": 80},
    )

    assert response.status_code == 503

