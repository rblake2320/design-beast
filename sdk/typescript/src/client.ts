/**
 * Lightweight TypeScript/JavaScript client for Beast Studio
 * (http://127.0.0.1:8787). Zero runtime dependencies — uses the platform
 * `fetch` (Node 18+, or any browser). See ../../../openapi.json for the
 * generated contract and ../../../AGENT_ACCESS.md for operational rules
 * this client does not itself enforce.
 *
 *   import { BeastStudioClient } from "beast-studio-client";
 *   const c = new BeastStudioClient();
 *   const expanded = await c.expand("a cozy reading nook");
 *   const job = await c.run({ brief: "a cozy reading nook", prompt: expanded.prompt,
 *                            variations: expanded.variations });
 *   const final = await c.wait(job.id);
 */
import type {
  AnimateDuration, AnimateQuality, AspectRatio, BackendAction, BackendInfo,
  ImageModel, JobStatus, RecipeInfo, SubmitResponse,
} from "./types.ts";
import { TERMINAL_PHASES } from "./types.ts";

export const DEFAULT_BASE_URL = "http://127.0.0.1:8787";

export class BeastStudioError extends Error {
  cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "BeastStudioError";
    this.cause = cause;
  }
}

export interface BeastStudioClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  raiseForStatus?: boolean;
  fetchImpl?: typeof fetch;
}

export class BeastStudioClient {
  readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly raiseForStatus: boolean;
  private readonly fetchImpl: typeof fetch;

  constructor(options: BeastStudioClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.raiseForStatus = options.raiseForStatus ?? false;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  // ---- transport ----

  private async request<T>(method: string, path: string, body?: unknown,
                           headers?: Record<string, string>): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await this.fetchImpl(url, {
        method,
        headers: body !== undefined
          ? { "Content-Type": "application/json", ...(headers ?? {}) }
          : headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (e) {
      throw new BeastStudioError(`${method} ${path} failed: ${(e as Error).message}`, e);
    } finally {
      clearTimeout(timer);
    }
    if (this.raiseForStatus && !res.ok) {
      throw new BeastStudioError(`${method} ${path} returned HTTP ${res.status}`);
    }
    try {
      return (await res.json()) as T;
    } catch (e) {
      throw new BeastStudioError(
        `${method} ${path} returned non-JSON (status ${res.status})`, e);
    }
  }

  private get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  private post<T>(path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
    return this.request<T>("POST", path, body, headers);
  }

  // ---- sync endpoints (result in the response) ----

  recipes(): Promise<RecipeInfo[]> {
    return this.get("/api/recipes");
  }

  /** `data` is a dataURL or raw base64 string. */
  upload(name: string, data: string): Promise<{ file: string } | { error: string }> {
    return this.post("/api/upload", { name, data });
  }

  expand(brief: string, recipe = "cinematic-scene"): Promise<Record<string, unknown>> {
    return this.post("/api/expand", { brief, recipe });
  }

  judge(file: string, brief: string): Promise<{ score: number; kill: boolean; fix: string }> {
    return this.post("/api/judge", { file, brief });
  }

  tts(text: string, voice = "af_heart"): Promise<{ file: string; url: string } | { error: string }> {
    return this.post("/api/tts", { text, voice });
  }

  backends(): Promise<BackendInfo[]> {
    return this.get("/api/backends");
  }

  backend(name: string, action: BackendAction): Promise<{ ok: boolean; note?: string }> {
    return this.post("/api/backend", { name, action });
  }

  health(): Promise<{ ok: boolean; db: boolean; disk_free_gb: number; active_jobs: string[] }> {
    return this.get("/api/health");
  }

  runs(): Promise<Array<{ id: string; brief: string; phase: string; kind: string }>> {
    return this.get("/api/runs");
  }

  // ---- async-submit endpoints (return {id, idempotent_replay}) ----

  run(req: {
    brief: string; prompt?: string; variations?: string[]; model?: ImageModel;
    aspectRatio?: AspectRatio; reference?: string; idempotencyKey?: string;
  }): Promise<SubmitResponse> {
    const headers = req.idempotencyKey ? { "Idempotency-Key": req.idempotencyKey } : undefined;
    return this.post("/api/run", {
      brief: req.brief, prompt: req.prompt ?? "", variations: req.variations ?? [],
      model: req.model ?? "local:flux.1-schnell", aspect_ratio: req.aspectRatio ?? "1:1",
      reference: req.reference ?? "",
    }, headers);
  }

  /** allowCloudFallback=true spends the human's Higgsfield credits — only
   * pass true when explicitly told to (AGENT_ACCESS.md rule 1). */
  refine(file: string, instruction: string, brief = "",
        allowCloudFallback = false): Promise<SubmitResponse> {
    return this.post("/api/refine", {
      file, instruction, brief, allow_cloud_fallback: allowCloudFallback,
    });
  }

  /** allowCloudFallback=true spends the human's Higgsfield credits — only
   * pass true when explicitly told to. */
  animate(req: {
    file: string; motion?: string; duration?: AnimateDuration;
    quality?: AnimateQuality; allowCloudFallback?: boolean;
  }): Promise<SubmitResponse> {
    return this.post("/api/animate", {
      file: req.file,
      motion: req.motion ?? "slow cinematic dolly-in, subtle ambient movement",
      duration: req.duration ?? 5, quality: req.quality ?? "fast",
      allow_cloud_fallback: req.allowCloudFallback ?? false,
    });
  }

  /** allowHostedFallback=true lets the image LEAVE this machine to NVIDIA's
   * hosted API — only pass true when explicitly told to. */
  to3d(file: string, allowHostedFallback = false): Promise<SubmitResponse> {
    return this.post("/api/to3d", { file, allow_hosted_fallback: allowHostedFallback });
  }

  /** `file` is runs/<id>/model.glb. */
  toUe(file: string): Promise<SubmitResponse> {
    return this.post("/api/to_ue", { file });
  }

  // ---- status / control ----

  status(runId: string): Promise<JobStatus> {
    return this.get(`/api/run/${encodeURIComponent(runId)}`);
  }

  cancel(runId: string): Promise<{ ok: boolean; comfy?: string; note?: string }> {
    return this.post(`/api/job/${encodeURIComponent(runId)}/cancel`, undefined);
  }

  retry(runId: string): Promise<SubmitResponse | { error: string }> {
    return this.post(`/api/job/${encodeURIComponent(runId)}/retry`, undefined);
  }

  /** URL of the SSE stream for this job — feed it to an `EventSource` in a
   * browser, or use streamEvents() below for a dependency-free async
   * generator that works in Node too. */
  eventsUrl(runId: string): string {
    return `${this.baseUrl}/api/events/${encodeURIComponent(runId)}`;
  }

  /** Yield each JSON status snapshot as the server emits it over SSE,
   * stopping after a terminal phase (done/failed/cancelled) or when the
   * stream closes. No EventSource dependency — works in Node and browsers. */
  async *streamEvents(runId: string): AsyncGenerator<JobStatus> {
    let res: Response;
    try {
      res = await this.fetchImpl(this.eventsUrl(runId));
    } catch (e) {
      throw new BeastStudioError(
        `GET /api/events/${runId} failed: ${(e as Error).message}`, e);
    }
    if (!res.body) {
      throw new BeastStudioError(`GET /api/events/${runId} returned no body`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const rawEvent = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          for (const line of rawEvent.split("\n")) {
            if (!line.startsWith("data:")) continue;
            const payload = line.slice("data:".length).trim();
            if (!payload) continue;
            const snap = JSON.parse(payload) as JobStatus;
            yield snap;
            if (snap.phase && TERMINAL_PHASES.includes(snap.phase)) return;
          }
        }
      }
    } finally {
      // cancel (not just releaseLock) so an early return — e.g. we already
      // saw the terminal phase — tells the server to stop sending and the
      // socket can close immediately instead of idling until some other
      // timeout fires.
      try {
        await reader.cancel();
      } catch {
        // already closed/errored — nothing to do
      }
    }
  }

  /** Block until the job reaches a terminal phase, return its final status.
   * Prefers SSE (one connection, pushed updates); falls back to polling
   * status() if useSse=false or the stream errors. */
  async wait(runId: string, options: {
    pollIntervalMs?: number; timeoutMs?: number; useSse?: boolean;
  } = {}): Promise<JobStatus> {
    const pollIntervalMs = options.pollIntervalMs ?? 3000;
    const useSse = options.useSse ?? true;
    const t0 = Date.now();
    const timedOut = () => options.timeoutMs !== undefined && Date.now() - t0 > options.timeoutMs;

    if (useSse) {
      try {
        let last: JobStatus | undefined;
        for await (const snap of this.streamEvents(runId)) {
          last = snap;
          if (timedOut()) break;
        }
        if (last && last.phase && TERMINAL_PHASES.includes(last.phase)) return last;
      } catch {
        // fall through to polling
      }
    }
    while (true) {
      const snap = await this.status(runId);
      if (snap.phase && TERMINAL_PHASES.includes(snap.phase)) return snap;
      if (timedOut()) {
        throw new BeastStudioError(
          `job ${runId} did not reach a terminal phase within ${options.timeoutMs}ms `
          + `(last phase: ${snap.phase})`);
      }
      await new Promise((r) => setTimeout(r, pollIntervalMs));
    }
  }
}
