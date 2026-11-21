"""FastAPI servis za bezbjedan obračun cijene rezervacije."""

import os
import secrets
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

API_KEY_ENV = "PRICE_API_KEY"

NightCount = Annotated[int, Field(strict=True, ge=1, le=30)]
NightPrice = Annotated[
    Decimal,
    Field(gt=Decimal("0"), le=Decimal("10000"), decimal_places=2),
]
DiscountRate = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1"), decimal_places=2),
]


class PriceRequest(BaseModel):
    """Validirani podaci potrebni za obračun cijene."""

    model_config = ConfigDict(extra="forbid")

    noci: NightCount
    cijena_noci: NightPrice
    popust: DiscountRate = Decimal("0")


class PriceResponse(BaseModel):
    """Rezultat obračuna, prikazan kao tačan decimalni iznos."""

    iznos: str
    valuta: Literal["EUR"] = "EUR"


class HealthResponse(BaseModel):
    """Odgovor javne provjere dostupnosti servisa."""

    status: Literal["ok"] = "ok"


app = FastAPI(
    title="Rezervacije API",
    description="Testiran i obezbijeđen API za obračun cijene rezervacije.",
    version="1.0.0",
)


async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Provjeri API ključ bez čuvanja tajne u izvornom kodu."""

    expected_key = os.getenv(API_KEY_ENV)
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servis nije konfigurisan.",
        )
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nedostaje API ključ.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Neispravan API ključ.",
        )


@app.get("/health", response_model=HealthResponse, tags=["sistem"])
async def health() -> HealthResponse:
    """Vrati stanje servisa bez otkrivanja osjetljivih podataka."""

    return HealthResponse()


@app.post("/cijena", response_model=PriceResponse, tags=["rezervacije"])
async def calculate_price(
    request: PriceRequest,
    _authorized: Annotated[None, Depends(verify_api_key)],
) -> PriceResponse:
    """Izračunaj konačnu cijenu i zaokruži je na dva decimalna mjesta."""

    total = (
        Decimal(request.noci) * request.cijena_noci * (Decimal("1") - request.popust)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return PriceResponse(iznos=f"{total:.2f}")

