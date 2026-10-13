# beast-studio-client (TypeScript)

Lightweight TypeScript/JavaScript client for Beast Studio. Zero runtime
dependencies — uses the platform `fetch`.

## Distribution

`npm pack` builds and ships JavaScript and TypeScript declarations in `dist/`.
An installed consumer can import `beast-studio-client` without a TypeScript
loader or source checkout. The private package stays local; packing it does
not publish it.

```bash
npm ci
npm run typecheck
npm pack
```

The source tests run with Node's TypeScript support. Consumers execute the
compiled JavaScript exports.

## Usage

```typescript
import { BeastStudioClient } from "beast-studio-client";

const c = new BeastStudioClient(); // defaults to http://127.0.0.1:8787

// quality-loop pattern (see AGENT_ACCESS.md): expand -> run -> wait
const expanded = await c.expand("a cozy reading nook") as any;
const job = await c.run({
  brief: "a cozy reading nook", prompt: expanded.prompt,
  variations: expanded.variations,
});
const final = await c.wait(job.id); // blocks until done/failed/cancelled
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
