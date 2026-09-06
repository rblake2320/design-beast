"""Source-checkout entry point for the shared installed SDK mobile command."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "python"))
from beast_studio_client.mobile import main

if __name__ == "__main__":
    raise SystemExit(main())
