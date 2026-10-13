// Verify the actual tarball from an unrelated consumer's node_modules.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const scratch = mkdtempSync(join(tmpdir(), "beast-package-"));
// npm.cmd requires cmd on Windows; commands contain only static arguments.
function npm(args, cwd) {
  return process.platform === "win32"
    ? execFileSync("cmd.exe", ["/d", "/s", "/c", `npm ${args.join(" ")}`], { cwd, encoding: "utf8" })
    : execFileSync("npm", args, { cwd, encoding: "utf8" });
}
try {
  npm(["pack", "--pack-destination", ".", "--json"], root);
  const name = JSON.parse(readFileSync(join(root, "package.json"))).version;
  const tarball = resolve(root, `beast-studio-client-${name}.tgz`);
  writeFileSync(join(scratch, "package.json"), '{"private":true,"type":"module"}');
  // Copy avoids shell quoting a workspace path with spaces.
  const { copyFileSync } = await import("node:fs");
  copyFileSync(tarball, join(scratch, "client.tgz"));
  npm(["install", "./client.tgz", "--ignore-scripts", "--no-audit", "--no-fund"], scratch);
  writeFileSync(join(scratch, "verify.mjs"), `
    import assert from "node:assert/strict";
    import http from "node:http";
    import { BeastStudioClient, BeastStudioError, VERSION } from "beast-studio-client";
    const client = new BeastStudioClient();
    assert.equal(client.eventsUrl("test"), "http://127.0.0.1:8787/api/events/test");
    assert.equal(VERSION, "1.0.0");
    const server = http.createServer((request, response) => {
      if (request.url.includes("events")) {
        response.writeHead(200, { "Content-Type": "text/event-stream" });
        response.flushHeaders();
      } else {
        response.end(JSON.stringify({ ok: true, db: true }));
      }
    });
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    try {
      const installed = new BeastStudioClient({ baseUrl: "http://127.0.0.1:" + server.address().port });
      assert.equal((await installed.health()).db, true);
      const start = performance.now();
      await assert.rejects(() => installed.wait("x", { timeoutMs: 100 }), BeastStudioError);
      assert.ok(performance.now() - start < 600);
      console.log("Installed tarball imported, called real HTTP, and enforced SSE deadline");
    } finally {
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
  `);
  process.stdout.write(execFileSync(process.execPath, ["verify.mjs"], { cwd: scratch, encoding: "utf8" }));
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
