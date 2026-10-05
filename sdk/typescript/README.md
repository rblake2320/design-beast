# beast-studio-client (TypeScript)

Lightweight TypeScript/JavaScript client for Beast Studio. Zero runtime
dependencies — uses the platform `fetch`.

## Distribution: compiled JavaScript and declarations

`npm pack` builds `dist/` with TypeScript's `rewriteRelativeImportExtensions`.
The installed package exports JavaScript plus type declarations, so ordinary
Node resolves it from `node_modules` without TypeScript stripping or build tools.
The supported Node minimum is 22.18; CI exercises Node 22 and 24 on Windows and Linux.
Source scripts can still import `src/index.ts` directly from a checkout.

```bash
npm ci
npm run typecheck
npm test
npm run test:package
```

`test:package` builds a real tarball, installs it into an unrelated directory,
and imports and executes the installed package with Node. No package is published.

## Usage

```typescript
import { BeastStudioClient } from "./sdk/typescript/src/index.ts";

const c = new BeastStudioClient(); // defaults to http://127.0.0.1:8787

// quality-loop pattern (see AGENT_ACCESS.md): expand -> run -> wait
const expanded = await c.expand("a cozy reading nook") as any;
const job = await c.run({
  brief: "a cozy reading nook", prompt: expanded.prompt,
  variations: expanded.variations,
});
const final = await c.wait(job.id, { timeoutMs: 120_000 }); // blocks until done/failed/cancelled
if (final.phase === "done") console.log("winner:", final.final);
else console.log("failed:", final.error);

// cancel a job, or retry a terminal one
await c.cancel(job.id);
await c.retry(job.id);

// stream progress yourself instead of wait()
for await (const snap of c.streamEvents(job.id)) console.log(snap.phase);

// credit/privacy flags are opt-in, never sent true unless you say so
await c.animate({ file: "runs/x/final.png", motion: "slow push-in",
                  allowCloudFallback: true }); // only if the human asked
```

## Tests

```bash
cd design-beast/sdk/typescript && node --test tests/
```

GPU-free, no live Beast Studio server. Sync/async-submit/status/cancel/retry
endpoints are tested against a fake `fetch`; `streamEvents()`/`wait()` are
tested end-to-end against a real, tiny local `http` server (no external
dependency) so the SSE frame-parsing is genuinely exercised, not just
mocked.

Finite `wait` deadlines cover connection setup, SSE reads, JSON body reads, and
polling sleeps. Expired waits close their transport. `streamEvents(id, { signal })`
accepts an AbortSignal for caller cancellation. Malformed or oversized events
raise BeastStudioError; an unavailable stream can fall back to durable polling.
