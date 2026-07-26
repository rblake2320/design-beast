"""Typed request/response shapes mirroring studio/server.py's Pydantic models.

Kept as plain TypedDicts (not pydantic) so this SDK has exactly one runtime
dependency (requests). These are for IDE/type-checker help only — the client
does not validate against them before sending; the server is the source of
truth (see ../../openapi.json, generated from the live FastAPI app).
"""
from typing import List, Literal, TypedDict

ImageModel = Literal[
    "local:flux.1-schnell", "local:flux.2-klein", "comfy:flux.1-schnell",
    "nim:flux.1-schnell", "nim:flux.1-dev", "gpt_image_2", "nano_banana_2",
    "z_image",
]
AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
AnimateQuality = Literal["fast", "cinema"]
AnimateDuration = Literal[3, 5]
BackendAction = Literal["start", "stop"]

# Terminal + non-terminal job phases actually emitted by the server
# (studio/jobs.py TERMINAL + the sub-phases server.py's _status() writes).
JobPhase = Literal[
    "queued", "running", "generating", "judging", "improving", "grading",
    "done", "failed", "cancelled",
]

# jobs.py's structured error codes (E_* constants).
ErrorCode = Literal[
    "VALIDATION", "BACKEND_DOWN", "CENSORED_BLANK", "JUDGE_REJECTED",
    "TIMEOUT", "CANCELLED", "ENGINE_ERROR", "INTERNAL",
]


class Candidate(TypedDict, total=False):
    i: int
    prompt: str
    state: str
    file: str
    score: float
    kill: bool
    fix: str
    error: str
    auto_improved: bool
    video: bool
    glb: bool


class JobStatus(TypedDict, total=False):
    """Response shape of GET /api/run/{id} and each SSE event payload."""
    id: str
    kind: str
    brief: str
    model: str
    phase: JobPhase
    error: str
    error_code: ErrorCode
    candidates: List[Candidate]
    winner: int
    final: str
    upscaled: bool
    video: bool
    glb: bool
    ue_asset: str


class SubmitResponse(TypedDict, total=False):
    """Response shape of every async-submit endpoint (run/refine/animate/
    to3d/to_ue)."""
    id: str
    idempotent_replay: bool


class ApiError(TypedDict, total=False):
    error: str
    code: str
