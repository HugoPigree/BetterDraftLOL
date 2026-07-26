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
    warmup_all_server_caches,
)
from suggest_draft import (
    suggest_ban,
    suggest_improvements,
    suggest_retrospective_bans,
    suggest_retrospective_picks,
)
from meta_status import get_meta_status
from bot_speech_builder import build_bot_explanation_steps
from match_simulator import resolve_simulation_phase, simulate_match, start_simulation
from player_signatures import get_player_signatures
from team_draft_bot import choose_team_bot_action
from lec_season import (
    build_playoff_bracket,
    build_standings,
    get_next_player_fixture,
    load_lec_meta,
    load_lec_teams,
    record_fixture_result,
    resolve_week_npc_matches,
    start_lec_season,
)
from worlds_teams import build_player_team, create_bracket, load_pro_teams, pick_opponent_teams

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


class DraftPickSlot(BaseModel):
    """Pick en cours de draft : le poste n'est pas encore connu."""

    model_config = ConfigDict(use_enum_values=True)

    champion: str = Field(min_length=1)
    role: Role | None = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_optional_role(cls, value: str | Role | None) -> str | Role | None:
        if value is None or value == "":
            return None
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
    estimated_champions: list[str] = Field(default_factory=list)


class MetaStatusResponse(BaseModel):
    latest_patch: str
    patches_available: list[str] = Field(default_factory=list)
    data_built_at: str | None = None
    oracle_updated_at: str | None = None
    oracle_status: str | None = None
    oracle_team_games: int | None = None
    meraki_updated_at: str | None = None
    meraki_champion_count: int | None = None
    ddragon_version: str | None = None
    ddragon_updated_at: str | None = None
    estimated_champions: list[str] = Field(default_factory=list)
    unmapped_champions: list[str] = Field(default_factory=list)
    schema_version: int = 0


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
    bot_picks: list[DraftPickSlot] = Field(default_factory=list, max_length=5)
    opponent_picks: list[DraftPickSlot] = Field(default_factory=list, max_length=5)
    patch: str = Field(min_length=1)
    available_champions: list[str] = Field(min_length=1)
    mode: Literal["mixed", "pro"] = "mixed"


class DraftBotMoveResponse(BaseModel):
    action: Literal["ban", "pick"]
    champion: str
    role: Role | None = None
    reason: str | None = None


class BotExplanationRequest(BaseModel):
    bot_picks: list[ChampionSlot] = Field(min_length=1, max_length=5)
    opponent_picks: list[ChampionSlot] = Field(default_factory=list, max_length=5)
    mode: Literal["mixed", "pro"] = "pro"


class WorldsRosterInput(BaseModel):
    TOP: str = Field(min_length=1)
    JUNGLE: str = Field(min_length=1)
    MIDDLE: str = Field(min_length=1)
    BOTTOM: str = Field(min_length=1)
    UTILITY: str = Field(min_length=1)


class WorldsStartRequest(BaseModel):
    team_name: str = Field(min_length=1)
    coach_name: str = Field(min_length=1)
    roster: WorldsRosterInput
    seed: int | None = None


class LecStartRequest(BaseModel):
    team_name: str = Field(min_length=1)
    coach_name: str = Field(min_length=1)
    roster: WorldsRosterInput
    replace_team_id: str | None = None
    seed: int | None = None


class LecRecordResultRequest(BaseModel):
    fixture_id: str = Field(min_length=1)
    winner_id: str = Field(min_length=1)
    fixtures: list[dict[str, Any]] = Field(min_length=1)
    teams: list[dict[str, Any]] = Field(min_length=1)
    week: int = Field(ge=1, le=9)


class WorldsTeamDraftBotRequest(DraftBotMoveRequest):
    team_id: str = Field(min_length=1)
    team_roster: WorldsRosterInput


class WorldsPredictionSnapshot(BaseModel):
    blue_win_probability: float = Field(ge=0.0, le=1.0)
    bot_lane_matchup: dict[str, Any] | None = None
    jungle_support_matchup: dict[str, Any] | None = None
    blue: dict[str, Any] = Field(default_factory=dict)
    red: dict[str, Any] = Field(default_factory=dict)


class WorldsSimulateMatchRequest(BaseModel):
    action: Literal["start", "resolve"] = "start"
    simulation_id: str | None = None
    simulation_token: str | None = None
    phase: Literal["early", "mid"] | None = None
    choice: Literal["engage", "temporize"] | None = None
    player_side: Literal["blue", "red"] = "blue"
    player_team_name: str = Field(default="", min_length=0)
    opponent_team_name: str = Field(default="", min_length=0)
    draft_blue_win_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    prediction: WorldsPredictionSnapshot | None = None
    opponent_team_id: str | None = None
    player_roster: WorldsRosterInput | None = None
    opponent_roster: WorldsRosterInput | None = None
    seed: int | None = None
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


def fetch_champion_catalog() -> tuple[dict[str, list[str]], list[str]]:
    from champion_catalog import (
        build_api_position_catalog,
        list_estimated_champion_names,
        load_unified_champions,
    )

    champions = load_unified_champions()
    catalog = build_api_position_catalog(champions)
    estimated = list_estimated_champion_names(champions)
    return catalog, estimated


DEFAULT_WARMUP_PATCH = "16.13"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        reset_predict_state()
        initialize_blue_side_winrate()
        warmup_ms = warmup_all_server_caches(DEFAULT_WARMUP_PATCH)
        logger.info("Caches inference préchargés en %.1f ms avant acceptation des requêtes", warmup_ms)
        logger.info(
            "API prête sur /health, /champions, /predict, /suggest-pick, "
            "/suggest-ban, /suggest-retrospective-ban, /suggest-retrospective-pick, "
            "/draft-bot/move, /bot-explanation, /meta/status, /worlds/* et /ask-chatbot-rules"
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
            catalog, estimated = fetch_champion_catalog()
        except Exception as exc:
            logger.error("Impossible de charger le catalogue champions: %s", exc)
            raise HTTPException(status_code=502, detail="Impossible de charger les champions") from exc

        names = sorted(catalog.keys())
        logger.info(
            "Liste champions servie (%d entrées, %d profils estimés)",
            len(names),
            len(estimated),
        )
        return ChampionsResponse(champions=names, positions=catalog, estimated_champions=estimated)

    @app.get("/meta/status", response_model=MetaStatusResponse)
    async def meta_status() -> dict[str, Any]:
        try:
            status = get_meta_status()
        except Exception as exc:
            logger.exception("Impossible de lire meta/status")
            raise HTTPException(status_code=502, detail="Statut data indisponible") from exc
        return status

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

    @app.get("/worlds/teams")
    async def worlds_teams() -> dict[str, Any]:
        try:
            teams = load_pro_teams()
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"teams": teams}

    @app.post("/worlds/start")
    async def worlds_start(request: WorldsStartRequest) -> dict[str, Any]:
        try:
            pro_teams = load_pro_teams()
            opponents = pick_opponent_teams(pro_teams, seed=request.seed)
            player_team = build_player_team(
                team_name=request.team_name,
                coach_name=request.coach_name,
                roster=request.roster.model_dump(),
            )
            bracket = create_bracket(player_team, opponents, seed=request.seed)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "player_team": player_team,
            "opponent_teams": opponents,
            "bracket": bracket,
        }

    @app.get("/worlds/signatures/{player_name}")
    async def worlds_player_signatures(player_name: str, role: Role) -> dict[str, Any]:
        try:
            signatures = get_player_signatures(player_name, role.value, top_n=8)
        except Exception as exc:
            logger.exception("Erreur signatures joueur")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "player": player_name,
            "role": role.value,
            "signatures": [
                {
                    "champion": item.champion,
                    "games": item.games,
                    "pick_rate": round(item.pick_rate, 4),
                    "winrate": round(item.winrate, 4),
                    "score": round(item.score, 2),
                }
                for item in signatures
            ],
        }

    @app.post("/worlds/draft-bot/move", response_model=DraftBotMoveResponse)
    async def worlds_draft_bot_move_endpoint(
        request: WorldsTeamDraftBotRequest,
    ) -> dict[str, Any]:
        try:
            return choose_team_bot_action(
                action_type=request.action_type,
                bot_side=request.bot_side,
                bot_picks=[slot.model_dump() for slot in request.bot_picks],
                opponent_picks=[slot.model_dump() for slot in request.opponent_picks],
                patch=request.patch.strip(),
                available_champions=request.available_champions,
                team_roster=request.team_roster.model_dump(),
                mode=request.mode,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Erreur interne pendant worlds/draft-bot/move")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/worlds/simulate-match")
    async def worlds_simulate_match_endpoint(
        request: WorldsSimulateMatchRequest,
    ) -> dict[str, Any]:
        if request.action == "resolve":
            if (not request.simulation_id and not request.simulation_token) or not request.phase or not request.choice:
                raise HTTPException(
                    status_code=400,
                    detail="simulation_token (ou simulation_id), phase et choice sont requis pour action=resolve.",
                )
            try:
                return resolve_simulation_phase(
                    simulation_id=request.simulation_id,
                    simulation_token=request.simulation_token,
                    phase=request.phase,
                    choice=request.choice,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                logger.exception("Erreur interne pendant worlds/simulate-match resolve")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        if not request.player_team_name.strip() or not request.opponent_team_name.strip():
            raise HTTPException(
                status_code=400,
                detail="player_team_name et opponent_team_name sont requis pour action=start.",
            )

        opponent_power = 0.55
        opponent_roster: dict[str, str] | None = None
        player_roster: dict[str, str] | None = None
        opponent: dict[str, Any] | None = None
        if request.player_roster:
            player_roster = request.player_roster.model_dump()
        if request.opponent_roster:
            opponent_roster = request.opponent_roster.model_dump()
        if request.opponent_team_id:
            try:
                teams = {team["id"]: team for team in load_pro_teams()}
                opponent = teams.get(request.opponent_team_id)
                if opponent:
                    if opponent.get("region") in {"LCK", "LPL"}:
                        opponent_power = 0.58
                    if opponent_roster is None:
                        opponent_roster = opponent.get("roster")
            except FileNotFoundError:
                pass
            if opponent is None:
                try:
                    lec_pool = {team["id"]: team for team in load_lec_teams()}
                    lec_opponent = lec_pool.get(request.opponent_team_id)
                    if lec_opponent:
                        opponent_power = float(lec_opponent.get("power_rating", 0.5))
                        if opponent_roster is None:
                            opponent_roster = lec_opponent.get("roster")
                except (FileNotFoundError, ValueError):
                    pass

        prediction_payload = (
            request.prediction.model_dump()
            if request.prediction
            else {
                "blue_win_probability": request.draft_blue_win_probability,
                "bot_lane_matchup": None,
                "jungle_support_matchup": None,
                "blue": {"score_final": 0.0, "score_synergie": 0.5},
                "red": {"score_final": 0.0, "score_synergie": 0.5},
            }
        )
        try:
            return start_simulation(
                player_side=request.player_side,
                player_team_name=request.player_team_name.strip(),
                opponent_team_name=request.opponent_team_name.strip(),
                draft_blue_win_prob=request.draft_blue_win_probability,
                prediction=prediction_payload,
                player_roster=player_roster,
                opponent_roster=opponent_roster,
                player_roster_power=0.5,
                opponent_roster_power=opponent_power,
                seed=request.seed,
            )
        except Exception as exc:
            logger.exception("Erreur interne pendant worlds/simulate-match start")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/lec/teams")
    async def lec_teams() -> dict[str, Any]:
        try:
            teams = load_lec_teams()
            meta = load_lec_meta()
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"teams": teams, **meta}

    @app.post("/lec/start-season")
    async def lec_start_season(request: LecStartRequest) -> dict[str, Any]:
        try:
            return start_lec_season(
                team_name=request.team_name,
                coach_name=request.coach_name,
                roster=request.roster.model_dump(),
                replace_team_id=request.replace_team_id,
                seed=request.seed,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/lec/record-result")
    async def lec_record_result(request: LecRecordResultRequest) -> dict[str, Any]:
        try:
            fixtures = [dict(fixture) for fixture in request.fixtures]
            teams = [dict(team) for team in request.teams]
            record_fixture_result(fixtures, request.fixture_id, request.winner_id)
            resolve_week_npc_matches(fixtures, teams, request.week, seed=None)
            standings = build_standings(fixtures, teams)
            next_fixture = get_next_player_fixture(fixtures, "player")
            regular_complete = next_fixture is None
            playoffs = build_playoff_bracket(standings, teams) if regular_complete else None
            player_row = next((row for row in standings if row.get("is_player_team")), None)
            return {
                "fixtures": fixtures,
                "standings": standings,
                "next_fixture": next_fixture,
                "regular_complete": regular_complete,
                "playoffs": playoffs,
                "player_rank": player_row["rank"] if player_row else None,
                "player_playoffs": bool(player_row and player_row["rank"] <= 6),
                "player_worlds": bool(player_row and player_row["rank"] <= 3),
            }
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
