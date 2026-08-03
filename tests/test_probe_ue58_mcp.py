import pytest

from scripts.probe_ue58_mcp import McpClient


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/mcp",
        "http://localhost:8000/mcp",
        "http://[::1]:8000/mcp",
    ],
)
def test_mcp_probe_accepts_only_loopback_examples(url):
    assert McpClient(url).url == url


def test_mcp_probe_rejects_remote_endpoint():
    with pytest.raises(ValueError, match="only loopback URLs are allowed"):
        McpClient("http://192.168.1.50:8000/mcp")
