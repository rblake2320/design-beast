# beast-studio-client (TypeScript)

Lightweight TypeScript/JavaScript client for Beast Studio. Zero runtime
dependencies — uses the platform `fetch`.

## Distribution model: source-only, no build step

This package ships `.ts` source and imports its own siblings with `.ts`
extensions (`allowImportingTsExtensions` in `tsconfig.json`). It runs
directly, unbuilt, on any TypeScript-native runtime:

- **Node 22.6+** — `node --experimental-strip-types` (or unflagged on newer
  Node; this repo was verified against Node 24) runs `.ts` files directly.
- **Deno / Bun** — native `.ts` execution, no config needed.
- **Older Node, or a browser bundle** — run your own `tsc`/esbuild/swc over
  `src/` first; `allowImportingTsExtensions` requires `noEmit` (or
  `emitDeclarationOnly`) in the *consuming* tsconfig, matching this
  package's own — see `tsconfig.json` here as a starting point, and rewrite
  the `.ts` import specifiers to `.js` if your bundler needs classic
  NodeNext-style output.

This tradeoff was made deliberately for this environment (no network access
to install a `typescript` devDependency at generation time) and to keep the
package genuinely zero-dependency for the common case (a Node 22+ agent
script). If your environment prefers a pre-built `dist/`, run `tsc` with
`allowImportingTsExtensions: false` and `.js`-suffixed imports instead — the
source is otherwise standard TS with no other exotic syntax.

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
