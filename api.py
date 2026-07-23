# Lancer le serveur en local :
# uvicorn api:app --reload --port 8001

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

import build_training_dataset as btd
from chatbot_rules import answer_question
from draft_bot import choose_bot_action
from champion_profile_stats import enrich_predict_response_descriptions
from predict_draft import (
    initialize_blue_side_winrate,
    predict_draft as run_predict_draft,
    reset_predict_state,
    setup_logging,
)
from suggest_draft import (
    suggest_ban,
    suggest_improvements,
    suggest_retrospective_bans,
    suggest_retrospective_picks,
)
from bot_speech_builder import build_bot_explanation_steps

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://better-draft-lol.vercel.app",
]
ALLOWED_ORIGIN_REGEX = r"https://.*\.vercel\.app"


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
    mode: Literal["mixed", "pro"] = "mixed"


class HealthResponse(BaseModel):
    status: str


class ChampionsResponse(BaseModel):
    champions: list[str]
    positions: dict[str, list[str]]


class ChampionForceDetail(BaseModel):
    champion: str
    role: Role
    winrate: float | None = None
    games: int | None = None
    insufficient_data: bool = False
    data_source: Literal["soloq", "pro"] | None = None


class AttributeProfile(BaseModel):
    damage_mean: float
    toughness_mean: float
    control_mean: float
    mobility_mean: float
    utility_mean: float


class MerakiRoleCount(BaseModel):
    role: str
    count: int


class SynergyContribution(BaseModel):
    champion: str
    role: Role
    marginal_points: float


class TeamSynergyInsight(BaseModel):
    contributions: list[SynergyContribution]
    top_contributor: SynergyContribution
    least_contributor: SynergyContribution
    explanation: str = ""


class DuoSynergyDetail(BaseModel):
    champions: list[str]
    score: float | None
    games: int
    is_fallback: bool
    insufficient_data: bool = False


class TeamDuoSynergies(BaseModel):
    duo_jungle_support: DuoSynergyDetail
    duo_bot_lane: DuoSynergyDetail


class SideDuoSynergies(BaseModel):
    blue: TeamDuoSynergies
    red: TeamDuoSynergies


class DuoAdvantage(BaseModel):
    stronger_side: Literal["blue", "red", "even"]
    difference: float
    insufficient_data: bool = False
    comparison_message: str | None = None
    insufficient_sides: list[Literal["blue", "red"]] = Field(default_factory=list)


class DuoDifferential(BaseModel):
    jungle_support_advantage: DuoAdvantage
    bot_lane_advantage: DuoAdvantage


class BotLaneMatchupDetail(BaseModel):
    blue_champions: list[str]
    red_champions: list[str]
    blue_win_probability: float | None
    games: int
    is_fallback: bool
    method: Literal["measured", "blended", "soloq_composite"]
    insufficient_data: bool = False


DuoMatchupDetail = BotLaneMatchupDetail


class TeamPredictionDetail(BaseModel):
    score_force: float | None
    score_synergie_brut: float
    score_synergie: float
    score_final: float
    champions: list[ChampionForceDetail]
    attribute_profile: AttributeProfile
    meraki_roles: list[MerakiRoleCount]
    force_partial: bool = False
    synergy_insight: TeamSynergyInsight


class PredictResponse(BaseModel):
    mode: Literal["mixed", "pro"] = "mixed"
    blue_win_probability: float
    red_win_probability: float
    blue: TeamPredictionDetail
    red: TeamPredictionDetail
    differential: AttributeProfile
    duo_synergies: SideDuoSynergies
    bot_lane_matchup: BotLaneMatchupDetail
    jungle_support_matchup: DuoMatchupDetail
    duo_differential: DuoDifferential
    warnings: list[str]


class SuggestPickRequest(BaseModel):
    team_side: Literal["blue", "red"] = "blue"
    team_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    role_to_improve: Role
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"


class PickSuggestion(BaseModel):
    champion: str
    win_probability: float
    gain_percentage_points: float
    delta_force: float
    delta_synergie: float
    delta_duo: float
    delta_total: float
    reason: str


class SuggestPickResponse(BaseModel):
    team_side: Literal["blue", "red"]
    role: Role
    current_win_probability: float | None
    suggestions: list[PickSuggestion]


class SuggestBanRequest(BaseModel):
    team_side: Literal["blue", "red"] = "blue"
    team_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(min_length=1, max_length=4)
    opponent_remaining_roles: list[Role] = Field(min_length=1)
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"


class BanSuggestion(BaseModel):
    champion: str
    best_opponent_role: Role
    opponent_win_probability: float
    threat_percentage_points: float
    delta_force: float
    delta_synergie: float
    delta_duo: float
    delta_total: float
    reason: str


class SuggestBanResponse(BaseModel):
    team_side: Literal["blue", "red"]
    baseline_opponent_win_probability: float | None
    suggestions: list[BanSuggestion]


class SuggestRetrospectiveBanRequest(BaseModel):
    team_side: Literal["blue", "red"] = "blue"
    team_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"


class RetrospectiveBanSuggestion(BaseModel):
    champion: str
    role: Role
    replacement_champion: str
    win_probability: float
    gain_percentage_points: float
    delta_force: float
    delta_synergie: float
    delta_duo: float
    delta_total: float
    reason: str


class SuggestRetrospectiveBanResponse(BaseModel):
    team_side: Literal["blue", "red"]
    current_win_probability: float | None
    suggestions: list[RetrospectiveBanSuggestion]


class RetrospectivePickSuggestion(BaseModel):
    role: Role
    current_champion: str
    champion: str
    win_probability: float
    gain_percentage_points: float
    delta_force: float
    delta_synergie: float
    delta_duo: float
    delta_total: float
    reason: str


class SuggestRetrospectivePickRequest(BaseModel):
    team_side: Literal["blue", "red"] = "blue"
    team_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(min_length=5, max_length=5)
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"
    picks_per_role: int = Field(default=3, ge=1, le=3)


class SuggestRetrospectivePickResponse(BaseModel):
    team_side: Literal["blue", "red"]
    current_win_probability: float | None
    suggestions: list[RetrospectivePickSuggestion]


class AskChatbotRulesRequest(BaseModel):
    question: str = Field(min_length=1)
    prediction_context: dict[str, Any]
    available_champions: list[str] = Field(min_length=1)


class AskChatbotRulesResponse(BaseModel):
    answer: str
    intent_detected: str


class DraftBotMoveRequest(BaseModel):
    action_type: Literal["ban", "pick"]
    bot_side: Literal["blue", "red"]
    bot_picks: list[ChampionSlot] = Field(default_factory=list, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(default_factory=list, max_length=5)
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"


class DraftBotMoveResponse(BaseModel):
    action: Literal["ban", "pick"]
    champion: str
    role: Role | None = None


class BotExplanationRequest(BaseModel):
    bot_picks: list[ChampionSlot] = Field(min_length=1, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(default_factory=list, max_length=5)
    mode: Literal["mixed", "pro"] = "pro"
    patch: str = Field(default="16.13", min_length=1)


class BotExplanationStep(BaseModel):
    champion: str | None = None
    role: Role | None = None
    text: str


class BotExplanationResponse(BaseModel):
    steps: list[BotExplanationStep]


POSITION_MAP = {
    "SUPPORT": "UTILITY",
}


def fetch_champion_names() -> list[str]:
    return sorted(fetch_champion_catalog().keys())


def fetch_champion_catalog() -> dict[str, list[str]]:
    champions = btd.load_meraki_champions(btd.MERAKI_URL, btd.DEFAULT_MERAKI_CACHE)
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
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        reset_predict_state()
        initialize_blue_side_winrate()
        logger.info(
            "API prête sur /health, /champions, /predict, /suggest-pick, "
            "/suggest-ban, /suggest-retrospective-ban, /suggest-retrospective-pick, "
            "/draft-bot/move, /bot-explanation et /ask-chatbot-rules"
        )
        yield

    app = FastAPI(
        title="DraftLoL Predict API",
        description="API locale pour prédire la probabilité de victoire d'une draft.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def strip_api_prefix(request: Request, call_next):
        # Vercel Services keep the /api prefix; local Vite proxy already strips it.
        path = request.scope.get("path", "")
        if path == "/api" or path.startswith("/api/"):
            request.scope["path"] = path[4:] or "/"
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_origin_regex=ALLOWED_ORIGIN_REGEX,
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
            "Prédiction demandée patch=%s mode=%s blue=%s red=%s",
            patch,
            request.mode,
            [slot["champion"] for slot in blue_team],
            [slot["champion"] for slot in red_team],
        )

        try:
            result = run_predict_draft(blue_team, red_team, patch=patch, mode=request.mode)
            result = enrich_predict_response_descriptions(result)
        except FileNotFoundError as exc:
            logger.error("Patch ou données introuvables: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            logger.error("Erreur de validation métier: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant la prédiction")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        logger.info(
            "Prédiction calculée: blue=%.2f%% red=%.2f%%",
            result["blue_win_probability"] * 100,
            result["red_win_probability"] * 100,
        )
        return result

    @app.post("/suggest-pick", response_model=SuggestPickResponse)
    async def suggest_pick_endpoint(request: SuggestPickRequest) -> dict[str, Any]:
        try:
            return suggest_improvements(
                team_picks=[slot.model_dump() for slot in request.team_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                role_to_improve=request.role_to_improve.value,
                patch=request.patch.strip(),
                available_champions=request.available_champions,
                team_side=request.team_side,
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant suggest-pick")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/suggest-ban", response_model=SuggestBanResponse)
    async def suggest_ban_endpoint(request: SuggestBanRequest) -> dict[str, Any]:
        try:
            return suggest_ban(
                available_champions=request.available_champions,
                opponent_partial_picks=[slot.model_dump() for slot in request.opponent_picks],
                opponent_remaining_roles=[role.value for role in request.opponent_remaining_roles],
                patch=request.patch.strip(),
                team_picks=[slot.model_dump() for slot in request.team_picks],
                team_side=request.team_side,
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant suggest-ban")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/suggest-retrospective-ban", response_model=SuggestRetrospectiveBanResponse)
    async def suggest_retrospective_ban_endpoint(
        request: SuggestRetrospectiveBanRequest,
    ) -> dict[str, Any]:
        try:
            return suggest_retrospective_bans(
                team_picks=[slot.model_dump() for slot in request.team_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                patch=request.patch.strip(),
                available_champions=request.available_champions,
                team_side=request.team_side,
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant suggest-retrospective-ban")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/suggest-retrospective-pick", response_model=SuggestRetrospectivePickResponse)
    async def suggest_retrospective_pick_endpoint(
        request: SuggestRetrospectivePickRequest,
    ) -> dict[str, Any]:
        try:
            return suggest_retrospective_picks(
                team_picks=[slot.model_dump() for slot in request.team_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                patch=request.patch.strip(),
                available_champions=request.available_champions,
                team_side=request.team_side,
                picks_per_role=request.picks_per_role,
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant suggest-retrospective-pick")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/draft-bot/move", response_model=DraftBotMoveResponse)
    async def draft_bot_move_endpoint(request: DraftBotMoveRequest) -> dict[str, Any]:
        try:
            return choose_bot_action(
                action_type=request.action_type,
                bot_side=request.bot_side,
                bot_picks=[slot.model_dump() for slot in request.bot_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                patch=request.patch.strip(),
                available_champions=request.available_champions,
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant draft-bot/move")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/bot-explanation", response_model=BotExplanationResponse)
    async def bot_explanation_endpoint(request: BotExplanationRequest) -> dict[str, Any]:
        try:
            steps = build_bot_explanation_steps(
                bot_picks=[slot.model_dump() for slot in request.bot_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                mode=request.mode,
            )
            return {"steps": steps}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant bot-explanation")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/ask-chatbot-rules", response_model=AskChatbotRulesResponse)
    async def ask_chatbot_rules_endpoint(
        request: AskChatbotRulesRequest,
    ) -> dict[str, str]:
        try:
            return answer_question(
                question=request.question.strip(),
                prediction_context=request.prediction_context,
                available_champions=request.available_champions,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant ask-chatbot-rules")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
