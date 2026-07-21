# Lancer le serveur en local :
# uvicorn api:app --reload --port 8000

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from build_training_dataset import (
    DEFAULT_MERAKI_CACHE,
    MERAKI_URL,
    load_meraki_champions,
)
from predict_draft import initialize_blue_side_winrate, setup_logging

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]


class Role(str, Enum):
    TOP = "TOP"
    JUNGLE = "JUNGLE"
    MIDDLE = "MIDDLE"
    BOTTOM = "BOTTOM"
    UTILITY = "UTILITY"


class ChampionSlot(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    champion: str = Field(min_length=1)
    role: Role

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: str | Role) -> str | Role:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class PredictRequest(BaseModel):
    blue_team: list[ChampionSlot] = Field(min_length=5, max_length=5)
    red_team: list[ChampionSlot] = Field(min_length=5, max_length=5)
    patch: str = Field(min_length=1)


class HealthResponse(BaseModel):
    status: str


class ChampionsResponse(BaseModel):
    champions: list[str]
    positions: dict[str, list[str]]


class ChampionForceDetail(BaseModel):
    champion: str
    role: Role
    winrate: float


class AttributeProfile(BaseModel):
    damage_mean: float
    toughness_mean: float
    control_mean: float
    mobility_mean: float
    utility_mean: float


class MerakiRoleCount(BaseModel):
    role: str
    count: int


class TeamPredictionDetail(BaseModel):
    score_force: float
    score_synergie_brut: float
    score_synergie: float
    score_final: float
    champions: list[ChampionForceDetail]
    attribute_profile: AttributeProfile
    meraki_roles: list[MerakiRoleCount]


class PredictResponse(BaseModel):
    blue_win_probability: float
    red_win_probability: float
    blue: TeamPredictionDetail
    red: TeamPredictionDetail
    differential: AttributeProfile
    warnings: list[str]


POSITION_MAP = {
    "SUPPORT": "UTILITY",
}


def fetch_champion_names() -> list[str]:
    return sorted(fetch_champion_catalog().keys())


def fetch_champion_catalog() -> dict[str, list[str]]:
    champions = load_meraki_champions(MERAKI_URL, DEFAULT_MERAKI_CACHE)
    catalog: dict[str, list[str]] = {}

    for key, payload in champions.items():
        name = str(payload.get("name", key)).strip()
        if not name:
            continue

        raw_positions = payload.get("positions", [])
        positions: list[str] = []
        for position in raw_positions:
            mapped = POSITION_MAP.get(str(position).upper(), str(position).upper())
            if mapped not in positions:
                positions.append(mapped)

        catalog[name] = positions

    return catalog


def create_app() -> FastAPI:
    app = FastAPI(
        title="DraftLoL Predict API",
        description="API locale pour prédire la probabilité de victoire d'une draft.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            location = " -> ".join(str(part) for part in error.get("loc", []))
            message = error.get("msg", "valeur invalide")
            errors.append(f"{location}: {message}")

        logger.warning("Requête invalide sur %s: %s", request.url.path, errors)
        return JSONResponse(
            status_code=400,
            content={"detail": errors},
        )

    @app.on_event("startup")
    async def startup() -> None:
        setup_logging()
        initialize_blue_side_winrate()
        logger.info("API prête sur /health, /champions et /predict")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/champions", response_model=ChampionsResponse)
    async def champions() -> ChampionsResponse:
        try:
            catalog = fetch_champion_catalog()
        except Exception as exc:
            logger.error("Impossible de charger la liste Meraki: %s", exc)
            raise HTTPException(status_code=502, detail="Impossible de charger les champions") from exc

        names = sorted(catalog.keys())
        logger.info("Liste champions servie (%d entrées)", len(names))
        return ChampionsResponse(champions=names, positions=catalog)

    @app.post("/predict", response_model=PredictResponse)
    async def predict(request: PredictRequest) -> dict[str, Any]:
        blue_team = [slot.model_dump() for slot in request.blue_team]
        red_team = [slot.model_dump() for slot in request.red_team]
        patch = request.patch.strip()

        logger.info(
            "Prédiction demandée patch=%s blue=%s red=%s",
            patch,
            [slot["champion"] for slot in blue_team],
            [slot["champion"] for slot in red_team],
        )

        try:
            from predict_draft import predict_draft as run_predict_draft

            result = run_predict_draft(blue_team, red_team, patch=patch)
        except FileNotFoundError as exc:
            logger.error("Patch ou données introuvables: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            logger.error("Erreur de validation métier: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        logger.info(
            "Prédiction calculée: blue=%.2f%% red=%.2f%%",
            result["blue_win_probability"] * 100,
            result["red_win_probability"] * 100,
        )
        return result

    return app


app = create_app()
