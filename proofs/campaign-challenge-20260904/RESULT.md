# Campaign challenge: prepared; creative execution blocked

Test package: `bench/campaign-challenge/`. Protocol revision 2 at `b806da7`;
product source implementation is the reviewed `cc28b34` condition. This is a
planned controlled revision challenge, not a surprise challenge.

Latest real preflight: `preflight-1788576854121063800/receipt.json` and `studio.log`.
The earlier receipt is retained under its original protocol hashes; no creative
run took place under either protocol revision.

Executed: a separate Python/Studio process with a disposable SQLite database,
actual HTTP health and OpenAPI requests, and actual GPU admission measurement.
The owned server was stopped before database cleanup. No existing process or
service was stopped, no model was loaded, and no generation credits were used.

Outcome: **resource_blocked**. The first receipt measured 15,237 MiB free VRAM;
the configured image admission requires 16,384 MiB and video admission requires
28,672 MiB, including protected reserve. The updated receipt retains its own
fresh measurement. The quality judge alone is admissible, but judging without
campaign outputs would not measure creative performance.

Creative outputs: **0/4 attempted**. Creative score: **not measured**.
Competitor arm: **not run**. Competitive winner: **none established**.
Do not translate resource denial into a zero artistic score or a competitor win.

To proceed: obtain sufficient free local GPU capacity or an explicitly selected
alternative compute condition, and record the owner's paid budget plus accessible
competitor account before launching Runway. Both operators receive identical
reference bytes, brief, complete protocol and known revision. Retain all media,
failures, cost, wall time and interventions; then use at least three independent
human raters. Model self-scores are diagnostics only.

Run the no-credit readiness check:

```powershell
python bench/campaign_preflight.py --out .beast/optimization-proof/campaign
```

Exit 2 means blocked/error; exit 0 means only that preflight prerequisites passed.
It never means the campaign has passed. The testing-qa-harness workflow guided
the fixed input/output contract and separate operational versus creative outcomes.
