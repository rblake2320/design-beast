# beast-studio-client (Python)

Lightweight Python client for Beast Studio. One dependency: `requests`.

```bash
pip install -e sdk/python --config-settings editable_mode=compat
```

```python
from beast_studio_client import BeastStudioClient

c = BeastStudioClient()  # defaults to http://127.0.0.1:8787

# quality-loop pattern (see AGENT_ACCESS.md): expand -> run -> wait
expanded = c.expand("a cozy reading nook")
job = c.run(brief="a cozy reading nook", prompt=expanded["prompt"],
            variations=expanded["variations"])
final = c.wait(job["id"])          # blocks until done/failed/cancelled
if final["phase"] == "done":
    print("winner:", final["final"])
else:
    print("failed:", final.get("error"))

# cancel a job, or retry a terminal one
c.cancel(job["id"])
c.retry(job["id"])

# stream progress yourself instead of wait()
for snapshot in c.stream_events(job["id"]):
    print(snapshot["phase"])

# credit/privacy flags are opt-in, never sent True unless you say so
c.animate(file="runs/x/final.png", motion="slow push-in",
          allow_cloud_fallback=True)  # only if the human asked for it
```

## Tests

```bash
cd design-beast && python -m pytest sdk/python/tests -q
```

GPU-free, no live server: `test_client.py` mocks `requests.Session`;
`test_openapi_contract.py` regenerates the OpenAPI schema against a
throwaway DB and checks it against the checked-in `openapi.json` and against
`BeastStudioClient`'s method coverage.
