"""Static safety contracts for the Spark deployment script.

GPU-free: this test reads the script only and never invokes systemd or Docker.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "deploy" / "spark-setup.sh").read_text()


def test_spark_setup_uses_private_process_umask():
    assert "set -euo pipefail\n" in SCRIPT
    assert "umask 077\n" in SCRIPT
    assert SCRIPT.index("umask 077\n") < SCRIPT.index('cd "$(dirname "$0")/.."')


def test_beast_service_enforces_private_umask():
    service = SCRIPT.split(
        'cat > "$HOME/.config/systemd/user/beast-studio.service" <<EOF',
        1,
    )[1].split("\nEOF", 1)[0]
    assert "UMask=0077" in service
    assert "ExecStartPre=/usr/bin/chmod -R go-rwx $ROOT" in service


def test_existing_checkout_is_hardened_before_service_start():
    harden = 'chmod -R go-rwx "$ROOT"'
    start = "systemctl --user enable --now beast-studio.service"
    assert harden in SCRIPT
    assert SCRIPT.index(harden) < SCRIPT.index(start)
