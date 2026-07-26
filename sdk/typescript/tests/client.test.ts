/**
 * GPU-free contract tests for the TypeScript SDK. No live Beast Studio
 * server — sync/async-submit/status/cancel/retry endpoints are tested
 * against a fake `fetch`; SSE streaming is tested against a real, tiny
 * Node http server (no external dependency) so streamEvents() is verified
 * end-to-end, not just against a mock.
 *
 *   cd design-beast/sdk/typescript && node --test tests/
 */
import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";
import { BeastStudioClient, BeastStudioError } from "../src/client.ts";

function fakeFetch(handler: (url: string, init?: RequestInit) => {
  status?: number; json?: unknown;
}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fn = (async (url: string | URL, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    const { status = 200, json = {} } = handler(u, init);
    return new Response(JSON.stringify(json), { status });
  }) as unknown as typeof fetch;
  return { fetchImpl: fn, calls };
}

// ---- sync endpoints: verify method/path/body shape ----

test("recipes() issues a GET to /api/recipes", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: [{ name: "a", title: "A" }] }));
  const c = new BeastStudioClient({ fetchImpl });
  const out = await c.recipes();
  assert.equal(calls[0].url, "http://127.0.0.1:8787/api/recipes");
  assert.equal(calls[0].init?.method, "GET");
  assert.deepEqual(out, [{ name: "a", title: "A" }]);
});

test("upload() posts name/data body", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { file: "x.png" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.upload("x.png", "data:image/png;base64,AAAA");
  const body = JSON.parse(String(calls[0].init?.body));
  assert.deepEqual(body, { name: "x.png", data: "data:image/png;base64,AAAA" });
});

test("backend() posts name/action body", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { ok: true } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.backend("nim-flux", "start");
  const body = JSON.parse(String(calls[0].init?.body));
  assert.deepEqual(body, { name: "nim-flux", action: "start" });
});

// ---- async-submit endpoints: privacy/credit flags default false ----

test("refine() defaults allow_cloud_fallback to false", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.refine("f.png", "make it red");
  const body = JSON.parse(String(calls[0].init?.body));
  assert.equal(body.allow_cloud_fallback, false,
    "refine() must default allow_cloud_fallback to False — sending true "
    + "unprompted spends credits (AGENT_ACCESS.md rule 1)");
});

test("animate() defaults allow_cloud_fallback to false, honors explicit true", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.animate({ file: "f.png" });
  assert.equal(JSON.parse(String(calls[0].init?.body)).allow_cloud_fallback, false);
  await c.animate({ file: "f.png", allowCloudFallback: true });
  assert.equal(JSON.parse(String(calls[1].init?.body)).allow_cloud_fallback, true);
});

test("to3d() defaults allow_hosted_fallback to false", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.to3d("f.png");
  const body = JSON.parse(String(calls[0].init?.body));
  assert.equal(body.allow_hosted_fallback, false,
    "to3d() must default allow_hosted_fallback to False — sending true "
    + "unprompted leaks the image off-machine (AGENT_ACCESS.md rule 1)");
});

test("run() defaults model to the free local backend", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.run({ brief: "a cozy reading nook" });
  const body = JSON.parse(String(calls[0].init?.body));
  assert.equal(body.model, "local:flux.1-schnell");
});

test("run() sends the idempotency key as a header", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.run({ brief: "x y z", idempotencyKey: "key-123" });
  const headers = calls[0].init?.headers as Record<string, string>;
  assert.equal(headers["Idempotency-Key"], "key-123");
});

test("toUe() posts {file}", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "j1" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.toUe("runs/20260101_x/model.glb");
  assert.equal(calls[0].url, "http://127.0.0.1:8787/api/to_ue");
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)),
    { file: "runs/20260101_x/model.glb" });
});

// ---- status / control ----

test("status() GETs /api/run/{id}", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { phase: "done" } }));
  const c = new BeastStudioClient({ fetchImpl });
  const out = await c.status("run1");
  assert.equal(calls[0].url, "http://127.0.0.1:8787/api/run/run1");
  assert.equal(out.phase, "done");
});

test("cancel() POSTs /api/job/{id}/cancel", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { ok: true } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.cancel("run1");
  assert.equal(calls[0].url, "http://127.0.0.1:8787/api/job/run1/cancel");
  assert.equal(calls[0].init?.method, "POST");
});

test("retry() POSTs /api/job/{id}/retry", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { id: "run2" } }));
  const c = new BeastStudioClient({ fetchImpl });
  await c.retry("run1");
  assert.equal(calls[0].url, "http://127.0.0.1:8787/api/job/run1/retry");
});

test("eventsUrl() builds the SSE URL without a network call", () => {
  const c = new BeastStudioClient();
  assert.equal(c.eventsUrl("run1"), "http://127.0.0.1:8787/api/events/run1");
});

test("run IDs are encoded as one path segment", async () => {
  const { fetchImpl, calls } = fakeFetch(() => ({ json: { phase: "done" } }));
  const c = new BeastStudioClient({ fetchImpl });
  const hostile = "../health?admin=1#fragment";
  const encoded = "..%2Fhealth%3Fadmin%3D1%23fragment";
  await c.status(hostile);
  assert.equal(calls[0].url, `http://127.0.0.1:8787/api/run/${encoded}`);
  assert.equal(c.eventsUrl(hostile),
    `http://127.0.0.1:8787/api/events/${encoded}`);
});

// ---- transport-level error handling ----

test("network failure raises BeastStudioError", async () => {
  const fetchImpl = (async () => { throw new Error("refused"); }) as unknown as typeof fetch;
  const c = new BeastStudioClient({ fetchImpl });
  await assert.rejects(() => c.health(), BeastStudioError);
});

test("API-level error is returned, not thrown, by default", async () => {
  const { fetchImpl } = fakeFetch(() => ({ status: 422, json: { error: "short brief" } }));
  const c = new BeastStudioClient({ fetchImpl });
  const out = await c.run({ brief: "ab" });
  assert.deepEqual(out, { error: "short brief" });
});

test("raiseForStatus opts into throwing on HTTP error status", async () => {
  const { fetchImpl } = fakeFetch(() => ({ status: 500, json: { error: "x" } }));
  const c = new BeastStudioClient({ fetchImpl, raiseForStatus: true });
  await assert.rejects(() => c.health(), BeastStudioError);
});

// ---- SSE: real end-to-end test against a tiny local http server ----

async function withSseServer(
  chunks: string[],
  fn: (baseUrl: string) => Promise<void>,
) {
  const server = http.createServer((req, res) => {
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    let i = 0;
    const pump = () => {
      if (i >= chunks.length) return res.end();
      res.write(chunks[i++]);
      setImmediate(pump);
    };
    pump();
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const addr = server.address();
  const port = typeof addr === "object" && addr ? addr.port : 0;
  try {
    await fn(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

test("streamEvents() parses real SSE frames and stops at a terminal phase", async () => {
  const frames = [
    'data: {"phase": "generating"}\n\n',
    'data: {"phase": "done", "final": "final.png"}\n\n',
    'data: {"phase": "done", "final": "final.png"}\n\n', // must not be reached
  ];
  await withSseServer(frames, async (baseUrl) => {
    const c = new BeastStudioClient({ baseUrl });
    const events = [];
    for await (const snap of c.streamEvents("run1")) events.push(snap);
    assert.deepEqual(events.map((e) => e.phase), ["generating", "done"]);
    assert.equal(events[events.length - 1].final, "final.png");
  });
});

test("wait() resolves from a real SSE stream at the terminal event", async () => {
  const frames = [
    'data: {"phase": "generating"}\n\n',
    'data: {"phase": "failed", "error": "boom"}\n\n',
  ];
  await withSseServer(frames, async (baseUrl) => {
    const c = new BeastStudioClient({ baseUrl });
    const out = await c.wait("run1");
    assert.deepEqual(out, { phase: "failed", error: "boom" });
  });
});

test("wait() falls back to polling when the SSE connection fails", async () => {
  let calls = 0;
  const fetchImpl = (async (url: string | URL) => {
    const u = String(url);
    if (u.includes("/api/events/")) throw new Error("refused");
    calls += 1;
    const json = calls > 1 ? { phase: "done" } : { phase: "running" };
    return new Response(JSON.stringify(json), { status: 200 });
  }) as unknown as typeof fetch;
  const c = new BeastStudioClient({ fetchImpl });
  const out = await c.wait("run1", { pollIntervalMs: 0 });
  assert.deepEqual(out, { phase: "done" });
  assert.equal(calls, 2);
});
