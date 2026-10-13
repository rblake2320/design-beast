// Exercise the published file layout from an unrelated npm consumer.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
function npm(args, cwd) {
  // Windows requires the .cmd shim. No dynamic paths are interpolated: npm
  // always works in cwd and uses fixed relative package names below.
  return process.platform === "win32"
    ? execFileSync("cmd.exe", ["/d", "/s", "/c", `npm ${args.join(" ")}`], { cwd, encoding: "utf8" })
    : execFileSync("npm", args, { cwd, encoding: "utf8" });
}

test("packed SDK imports as JavaScript from consumer node_modules", () => {
  const scratch = mkdtempSync(join(tmpdir(), "beast-sdk-distribution-"));
  const packed = npm(["pack", "--json"], root);
  const info = JSON.parse(packed.slice(packed.indexOf("[")))[0];
  assert.ok(info.files.some(file => file.path === "dist/index.js"));
  assert.ok(info.files.some(file => file.path === "dist/index.d.ts"));
  assert.equal(info.files.some(file => file.path.startsWith("src/")), false);
  copyFileSync(join(root, info.filename), join(scratch, "client.tgz"));
  writeFileSync(join(scratch, "package.json"), '{"private":true,"type":"module"}');
  npm(["install", "./client.tgz", "--ignore-scripts", "--no-audit", "--no-fund"], scratch);
  writeFileSync(join(scratch, "probe.mjs"), `
    import assert from "node:assert/strict";
    import { BeastStudioClient, VERSION } from "beast-studio-client";
    assert.equal(VERSION, "1.0.0");
    assert.equal(new BeastStudioClient().eventsUrl("owned"), "http://127.0.0.1:8787/api/events/owned");
    assert.ok(import.meta.resolve("beast-studio-client").endsWith("/dist/index.js"));
    console.log("worked");
  `);
  assert.match(execFileSync(process.execPath, ["probe.mjs"], { cwd: scratch, encoding: "utf8" }), /worked/);
  // Keep package metadata and the actual installed consumer as retained proof.
  writeFileSync(join(scratch, "packed.json"), JSON.stringify(info, null, 2));
  console.log(`Installed SDK distribution evidence: ${scratch}`);
  assert.equal(JSON.parse(readFileSync(join(scratch, "packed.json"))).version, VERSION_FROM_PACKAGE());
});

function VERSION_FROM_PACKAGE() {
  return JSON.parse(readFileSync(join(root, "package.json"))).version;
}
