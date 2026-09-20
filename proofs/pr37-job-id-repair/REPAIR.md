# PR37 job-ID allocation repair

Base: `56889569d2fcdd15f2c56ad4f0f77ca007cb919d` (PR37 original reviewed head).
Original CI remains a failure: [run35400770909](https://github.com/rblake2320/design-beast/actions/runs/35400770909),
`studio/tests/test_cancel.py::test_run_loop_observes_cancel_with_zero_completions`,
`sqlite3.IntegrityError: UNIQUE constraint failed: jobs.id`, `studio/jobs.py:130`.
This repair does not replace that run or claim it passed.

## Mechanism and escape

The old allocator appended only four UUID hex characters to a second-resolution
timestamp. Two different UUIDs sharing that prefix during one second collided.
`test_same_second_shared_uuid_prefix_does_not_collide` deterministically reproduced
the same SQLite failure against the unchanged implementation; `before.xml`
retains that execution (five failures, one pass). The original cancellation test
used random IDs and did not deliberately force a collision. A neighboring defect
also reproduced: the idempotency lookup happened before locking, allowing two
threads to both miss the key before one failed its insert. Failed inserts left
the thread-local connection in a transaction.

## Repair and controls

Use all 32 UUID hex characters. Three insertion attempts handle a repeated full
ID through `ON CONFLICT(id) DO NOTHING`, never replacement. Other constraint or
operational errors propagate. Exhaustion raises an explicit error. A connection
transaction commits only successful outcomes and rolls back exceptional exits.
`BEGIN IMMEDIATE` serializes idempotency lookup plus insertion across SQLite
connections. The existing Python write lock remains. Empty non-null keys now
replay consistently with the database UNIQUE constraint.

SQLite's [UPSERT documentation](https://www.sqlite.org/lang_upsert.html) defines
the named conflict target and excludes NOT NULL failures from its handling;
[transaction documentation](https://www.sqlite.org/lang_transaction.html) defines
IMMEDIATE's write reservation and possible SQLITE_BUSY failure. Real temporary
SQLite tests check these behaviors; no database substitute is used.

## Executed results

- `before.xml`: unchanged implementation, six initial regressions: five failed,
  one passed. Original failures retained verbatim.
- `after-focused.xml`: six initial regressions plus cancellation tests:18 passed.
- `after-boundaries.xml`: final eight creation tests:8 passed, including concurrent
  independent connections with and without the shared Python lock, idempotency
  replay without new allocation, NOT NULL propagation/rollback, ID exhaustion,
  exact-collision retry and common-prefix distinct IDs.
- `after-final.xml`: final full non-live suite:354 passed,1 skipped,7 deselected.
  Skip: `watch/tests/test_inspection.py::test_planned_symlink_rejected_before_write`
  (Windows symlink privilege unavailable).
- Ruff `--select E9,F63,F7,F82`:passed. `beast_core.py validate`:passed.
- Doctor:31 OK, optional ComfyUI offline, ffmpeg and ffprobe absent from PATH.
  This task executed no media or GPU work.

Finite class sweep (`studio` and `scripts`, Python files): the sole production
`INSERT INTO jobs` and timestamp/UUID allocator is this function. Remaining
truncated UUID is an eight-character live-test idempotency fixture, not a job-ID
allocator. `test_state_authority.py` also inserts explicit fixture IDs. Production
callers route through `server.py` to `jobs.create`; no alternate allocator changed.

All eight new tests use real disposable SQLite; UUID/time injection creates
deterministic collisions and no-lock injection tests connection serialization.
Cancellation tests retain their synthetic backends. No live server, GPU, provider,
production retry/cancellation, scale or release claim is made. SQLite may still
return busy/operational errors under external contention; these are not hidden.
Existing stored IDs remain valid and unchanged. Long UUID IDs passed the retained
non-live suite; external integrations were not exercised.

The original CI run needs exact-head CI and fresh independent review on the
repair before PR37 is eligible for a merge decision. Builder has not pushed,
approved, marked ready, merged, or altered downstream Watch proofs.
