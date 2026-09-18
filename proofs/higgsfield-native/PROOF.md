# Native Higgsfield and live Studio acceptance

## Outcome (2026-09-18)

The local CLI completed browser OAuth, selected the sole owner Ultra workspace,
and retrieved the previous MCP-generated job through native `generate get` and
`generate wait`. No credential material is retained in this repository.

The actual native adapter then submitted a new reference refinement, received
completed job `3f892fd2-6875-43f1-874a-3a72d48fadf3`, downloaded its result through
validated HTTPS, decoded a 5504 x 3072 PNG, and recorded its hash and native job
identity. The CLI resolves requested `nano_banana_2` to `nano_banana_pro` in this
installed version; requested and returned identifiers are both retained.

Native cost preflight reported 4 credits. Balance before this job: 2971; after:
2967. Combined with the preceding creative comparison, spending is 33 of the
owner-authorized 500 credits. No retry or replacement job was submitted.

The same image was uploaded to the running, unmocked Studio HTTP server, then
selected through its saved-source picker in Edge. The browser reported loaded
pixels at 5504 x 3072. `studio-live.png` shows the selected source and rendered
image. An independent reviewer compared the native and uploaded bytes and
inspected the screenshot. This closes native authentication, native artifact
generation, and live source-selection/rendering acceptance. It does not claim
the separate GPU-dependent Run the Loop workflow was exercised: the live GPU
admission check denied new work with approximately 2 GiB free, and no user
process was stopped or guard bypassed. Generation was initiated by the committed
proof command using the same adapter delegated to by Studio's `hf_generate`.

## Repair and regression evidence

- Failed behavior: regex extracted an input URL even when CLI returned failure.
- Cause: no process/status boundary and no distinction between input and output.
- Escape: prior tests did not exercise failed CLI stdout containing media URLs.
- Sweep: all three Studio cloud call sites delegate to the one repaired helper.
- Control: strict job JSON, completed status, actual result field, unique receipt
  reservation, no automatic replay, bounded allowlisted downloads, decoded media,
  and atomic no-overwrite publication. Windows npm shim resolves to native hf.exe.
- Tests: 171 Studio tests passed, 7 explicitly live-GPU tests deselected by the
  repository default. Tests include malformed/duplicate JSON, unsafe URLs,
  redirects, truncation, byte/deadline limits, timeout, concurrent/repeated intent,
  existing output preservation, invalid media, and saved-source listing.
- Ownership: helper independently reviewed by parent; parent UI changes reviewed
  by the other agent. No self-merge.

Repeat the zero-credit live integrity check while Studio is running:

    python scripts/prove_higgsfield_native.py --verify-only

The paid command refuses an existing output/intent and is deliberately not a
retry button. New paid experiments require their own explicit preflight and
destination. CDN allowlist changes require inspection. Image validation is
proven here; the video branch has not been exercised by this image task.

## Visible UI improvements

Studio can now reopen saved source images without repeating a browser upload.
Filenames are inserted using DOM text nodes rather than innerHTML. The old
unconditional "nothing leaves this machine" headline was corrected because
selected cloud engines do send prompts and references to their providers.

Browser automation's file chooser timed out and a large clipboard transfer
disconnected its bridge; those routes are not credited as passed. The retained
acceptance uses the real HTTP intake and live saved-source selection instead.

Studio is served from this isolated worktree at http://127.0.0.1:8787. No edits
were made to the dirty canonical checkout, Vigil, PhoneClaw, or Unreal projects.
