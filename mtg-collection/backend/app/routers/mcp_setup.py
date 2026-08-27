"""MCP Setup endpoints — proxy download and config instructions."""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

router = APIRouter()

PROXY_PATH = Path("/app/mcp-proxy.mjs")


@router.get("/proxy.mjs")
async def download_proxy():
    """Serve the mcp-proxy.mjs file as download."""
    if not PROXY_PATH.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"error": "mcp-proxy.mjs not found in container"},
            status_code=404,
        )
    return FileResponse(
        PROXY_PATH,
        filename="mcp-proxy.mjs",
        media_type="application/javascript",
        headers={"Content-Disposition": "attachment; filename=mcp-proxy.mjs"},
    )


@router.get("/setup-instructions")
async def setup_instructions(request: Request):
    """Generate ready-to-paste Claude Desktop config + download URL.

    The proxy (mcp-proxy.mjs) takes POSITIONAL arguments:
        node mcp-proxy.mjs <ha_url> <ha_token> <ingress_path>/mcp [mcp_auth_token]
    An earlier version of this endpoint emitted MTG_* environment variables the
    proxy never reads, and pointed at /mcp/sse, which does not exist — the
    generated config could not work.
    """
    from ..config import get_settings
    from ..services.ingress import ingress_base

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/api/mcp/proxy.mjs"

    ingress = ingress_base()  # "" outside a Supervisor environment
    mcp_ingress_path = f"{ingress}/mcp" if ingress else "<INGRESS_PATH>/mcp"

    auth_configured = bool(get_settings().mcp_auth_token)
    args = [
        "<PATH_TO>/mcp-proxy.mjs",
        "<YOUR_HA_URL e.g. https://ha.example.net>",
        "<YOUR_HA_LONG_LIVED_TOKEN>",
        mcp_ingress_path,
    ]
    if auth_configured:
        args.append("<MCP_AUTH_TOKEN from the add-on options>")

    config_example = {
        "mcpServers": {
            "mtg-collection": {
                "command": "node",
                "args": args,
            }
        }
    }

    steps = [
        {"step": 1, "text": "Download mcp-proxy.mjs and save it to a permanent location"},
        {"step": 2, "text": "Run 'npm install ws' once in that location (the proxy needs the ws package)"},
        {"step": 3, "text": "Generate a long-lived access token in Home Assistant (profile → security)"},
        {"step": 4, "text": "Copy the config snippet below into claude_desktop_config.json"},
        {"step": 5, "text": "Replace <PATH_TO>, <YOUR_HA_URL> and <YOUR_HA_LONG_LIVED_TOKEN>"},
    ]
    if auth_configured:
        steps.append({"step": 6, "text": "Append the mcp_auth_token from the add-on configuration as the last argument"})
    steps.append({"step": len(steps) + 1, "text": "Restart Claude Desktop"})

    return {
        "download_url": download_url,
        "mcp_ingress_path": mcp_ingress_path,
        "auth_required": auth_configured,
        "config_example": config_example,
        "instructions": steps,
        "config_paths": {
            "macos": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "windows": "%APPDATA%\\Claude\\claude_desktop_config.json",
            "linux": "~/.config/Claude/claude_desktop_config.json",
        },
    }
