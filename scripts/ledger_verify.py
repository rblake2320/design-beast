"""beast ledger — verify the hash-chained provenance ledger offline."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "studio"))

import ledger  # noqa: E402

ok, message = ledger.verify(REPO / "studio" / "runs" / ledger.LEDGER_NAME)
print(("OK: " if ok else "TAMPERED: ") + message)
sys.exit(0 if ok else 1)
