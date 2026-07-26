/**
 * Typed request/response shapes mirroring studio/server.py's Pydantic
 * models. See ../../../openapi.json for the generated contract this file
 * is hand-kept in sync with.
 */

export type ImageModel =
  | "local:flux.1-schnell" | "local:flux.2-klein" | "comfy:flux.1-schnell"
  | "nim:flux.1-schnell" | "nim:flux.1-dev"
  | "gpt_image_2" | "nano_banana_2" | "z_image";

export type AspectRatio = "1:1" | "16:9" | "9:16" | "4:3" | "3:4";
export type AnimateQuality = "fast" | "cinema";
export type AnimateDuration = 3 | 5;
export type BackendAction = "start" | "stop";

/** Terminal + non-terminal job phases actually emitted by the server. */
export type JobPhase =
  | "queued" | "running" | "generating" | "judging" | "improving" | "grading"
  | "done" | "failed" | "cancelled";

/** jobs.py's structured error codes (E_* constants). */
export type ErrorCode =
  | "VALIDATION" | "BACKEND_DOWN" | "CENSORED_BLANK" | "JUDGE_REJECTED"
  | "TIMEOUT" | "CANCELLED" | "ENGINE_ERROR" | "INTERNAL";

export const TERMINAL_PHASES: readonly JobPhase[] = ["done", "failed", "cancelled"];

export interface Candidate {
  i: number;
  prompt?: string;
  state?: string;
  file?: string;
  score?: number;
  kill?: boolean;
  fix?: string;
  error?: string;
  auto_improved?: boolean;
  video?: boolean;
  glb?: boolean;
}

/** Response shape of GET /api/run/{id} and each SSE event payload. */
export interface JobStatus {
  id?: string;
  kind?: string;
  brief?: string;
  model?: string;
  phase?: JobPhase;
  error?: string;
  error_code?: ErrorCode;
  candidates?: Candidate[];
  winner?: number;
  final?: string;
  upscaled?: boolean;
  video?: boolean;
  glb?: boolean;
  ue_asset?: string;
  [extra: string]: unknown;
}

/** Response shape of every async-submit endpoint (run/refine/animate/to3d/to_ue). */
export interface SubmitResponse {
  id: string;
  idempotent_replay?: boolean;
}

export interface ApiError {
  error: string;
  code?: string;
}

export interface RecipeInfo {
  name: string;
  title: string;
}

export interface BackendInfo {
  name: string;
  state: string;
  ready: boolean;
  port: number;
}
