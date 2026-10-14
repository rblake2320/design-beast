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

## Bounded waits

Pass a timeout when the caller needs a total wait budget:

```python
from beast_studio_client import BeastStudioError

try:
    final = c.wait(job["id"], timeout=120)
except BeastStudioError as error:
    print(error)  # timeout, transport failure, or unsupported caller policy
```

The budget covers SSE and polling, DNS, connections, TLS and HTTP retry delays.
Each bounded wait uses its own connection pools so its cleanup does not close
another caller's connections. A wait timeout stops waiting for the job; use
`c.cancel(job["id"])` to request cancellation of the server job.

A bounded wait supports a stock `requests.Session` and standard settings. It
refuses custom session or adapter methods, authentication callbacks, response
hooks and customized pool or proxy behavior that it cannot preserve within the
deadline. That refusal happens before a request is sent. `wait()` without a
timeout retains the supplied session's behavior and has no total wait deadline.

## Tests

```bash
cd design-beast && python -m pytest sdk/python/tests -q
```

These tests require no GPU or external service. `test_client.py` mocks `requests.Session`;
`test_openapi_contract.py` regenerates the OpenAPI schema against a
throwaway DB and checks it against the checked-in `openapi.json` and against
`BeastStudioClient`'s method coverage. `test_deadline_claude_ld.py` starts owned
loopback HTTP/TLS servers and exercises real transport deadlines and cleanup.
For fresh wheel and npm tarball acceptance against a disposable Studio server,
run `python scripts/verify_sdk_distribution_codex_ld.py` from the repository
root in a fresh checkout with no Studio database.
