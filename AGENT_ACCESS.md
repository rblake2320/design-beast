# Beast Studio — Agent Access

Local AI production API on the RTX 5090. Base URL: `http://127.0.0.1:8787` (this
machine only). Four sections: paste block · API contract · safety rules · worked example.

---

## 1 · Paste block (minimum viable access)

```
Beast Studio API at http://127.0.0.1:8787. Async endpoints (/api/run, /api/refine,
/api/animate, /api/to3d, /api/to_ue) return {id} immediately — poll /api/run/{id}
every 5-10s until phase is "done" or "failed" (failed carries .error). Sync endpoints
(/api/upload, /api/expand, /api/judge, /api/tts) return results directly.
Default model is local:flux.1-schnell (free). Cloud fallback NEVER happens unless you
send allow_cloud_fallback:true (it spends the human's Higgsfield credits — don't,
unless told to). Full contract: C:\Users\techai\design-beast\AGENT_ACCESS.md
Smoke test: curl.exe -sS http://127.0.0.1:8787/api/recipes
```

## 2 · API contract

**Sync** (result in the response):

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/recipes` | — | `[{name, title}]` |
| `POST /api/expand` | `{"brief":"make a cat dog","recipe":"cinematic-scene"}` | `{"prompt":"…","axis":"lighting","variations":["…",4],"model_used":"qwen3.6:27b"}` |
| `POST /api/upload` | `{"name":"x.png","data":"<dataURL or base64>"}` | `{"file":"223045_x.png"}` |
| `POST /api/judge` | `{"file":"223045_x.png","brief":"…"}` | `{"score":7,"kill":false,"fix":"one sentence"}` |
| `POST /api/tts` | `{"text":"hello"}` | `{"file":"tts_….wav","url":"/uploads/tts_….wav"}` |
| `GET /api/backends` | — | `[{name,state,ready,port}]` |
| `POST /api/backend` | `{"name":"nim-flux","action":"start"}` | `{"ok":true,"note":"…"}` |

**Async** (returns `{"id":"20260725_223045_a1b2"}`; poll `GET /api/run/{id}`):

| Endpoint | Request fields |
|---|---|
| `POST /api/run` | `brief` (required), `prompt`, `variations[]`, `model` (default `local:flux.1-schnell`), `aspect_ratio` (`1:1\|16:9\|9:16\|4:3\|3:4`), `reference` (Higgsfield models ONLY — 400 error with local/nim models) |
| `POST /api/refine` | `file`, `instruction`, `brief`, `allow_cloud_fallback` (default false) |
| `POST /api/animate` | `file`, `motion`, `duration` (3\|5), `quality` (`"fast"`=Wan silent ~3min · `"cinema"`=LTX-2.3 with generated audio ~25min), `allow_cloud_fallback` |
| `POST /api/to3d` | `file`, `allow_hosted_fallback` (default false — true lets the image LEAVE this machine to NVIDIA's hosted API) → `model.glb` (TRELLIS auto-starts, warmup ~5min) |
| `POST /api/to_ue` | `file:"runs/<id>/model.glb"` → StaticMesh in the RouteRush UE 5.6 project (NOT the UE 5.8/BeastLab MCP instance — those are separate engines) |

**Poll responses** — success and failure shapes:

```json
{"id":"20260725_223045_a1b2","phase":"done","winner":3,"final":"final.png",
 "candidates":[{"i":3,"state":"done","score":8,"kill":false,"fix":"…"}]}

{"id":"20260725_223045_a1b2","phase":"failed","error":"specific, actionable reason"}
```

`file` fields accept an uploads filename or `runs/<id>/<file>`. Outputs on disk:
`C:\Users\techai\design-beast\studio\runs\<id>\` → `final.png` (2048², validated
upscale + grade), `clip.mp4`, `model.glb`.

Models for `/api/run`: `local:flux.1-schnell` (default, ~7s/img), `local:flux.2-klein`
(newest), `nim:flux.1-schnell|dev` (hosted, free, slow queue), `gpt_image_2` /
`nano_banana_2` / `z_image` (**Higgsfield — spends credits**).

## 3 · Credit-safety & operational rules

1. **Money & privacy:** the default path is 100% local and free — nothing leaves the
   machine and nothing spends credits unless YOU opt in. `allow_cloud_fallback:true`
   spends the human's Higgsfield credits; `allow_hosted_fallback:true` (to3d) sends
   the image to NVIDIA's hosted API. Send neither unless the human explicitly asked.
2. **Judge verdicts, operationally:**
   - `kill:true` → discard that candidate; never deliver it.
   - `score ≤ 3` → not deliverable; the run loop already refuses such winners.
   - Black/censored frame (error says "blank frame … content-safety filter") →
     the NIM guardrail censored it. Change wording/subject; do NOT retry unchanged.
   - Other low scores → feed the `fix` text into a new variation or `/api/refine`.
3. **Backends are shared machine state.** Before starting anything, record
   `GET /api/backends`. When your task ends, stop ONLY services that you moved from
   stopped→running. Never stop something that was already running — another agent or
   the human may be using it.
4. **VRAM:** don't run `quality:"cinema"` (22B) at the same time as image generation.
   Cold backends take minutes on first call — the run card streams warmup progress;
   poll patiently instead of declaring failure.
5. **Quality method:** never one-shot a deliverable. `/api/expand` → 4 one-axis
   variations → `/api/run` → act on the judge's `fix`. Recipe cards:
   `design-system/recipes/`.

## 4 · Canonical end-to-end example

```bash
# 1. expand a vague brief (sync, free)
curl.exe -sS -X POST http://127.0.0.1:8787/api/expand -H "Content-Type: application/json" ^
  -d "{\"brief\":\"a cozy reading nook\",\"recipe\":\"cinematic-scene\"}"
# → take .prompt and .variations from the response

# 2. run the loop (async, free, local)
curl.exe -sS -X POST http://127.0.0.1:8787/api/run -H "Content-Type: application/json" ^
  -d "{\"brief\":\"a cozy reading nook\",\"prompt\":\"<expanded>\",\"variations\":[\"<v1>\",\"<v2>\",\"<v3>\",\"<v4>\"]}"
# → {"id":"<RUN>"}

# 3. poll until terminal
curl.exe -sS http://127.0.0.1:8787/api/run/<RUN>
# phase "done" → deliverable is studio\runs\<RUN>\final.png
# phase "failed" → read .error, fix the cause, retry ONCE with changes

# 4. optional: animate the winner (silent, fast tier)
curl.exe -sS -X POST http://127.0.0.1:8787/api/animate -H "Content-Type: application/json" ^
  -d "{\"file\":\"runs/<RUN>/final.png\",\"motion\":\"slow push-in, dust motes in light\",\"duration\":5,\"quality\":\"fast\"}"
```

If connection refused: `cd C:\Users\techai\design-beast && python studio/server.py`
