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
    """Generate ready-to-paste Claude Desktop config + download URL."""
    base_url = str(request.base_url).rstrip("/")

    download_url = f"{base_url}/api/mcp/proxy.mjs"
    sse_endpoint = f"{base_url}/mcp/sse"

    config_example = {
        "mcpServers": {
            "mtg-collection": {
                "command": "node",
                "args": ["<PATH_TO>/mcp-proxy.mjs"],
                "env": {
                    "MTG_BASE_URL": base_url,
                    "MTG_TOKEN": "<TODO: your long-lived token>",
                    "MTG_SSE_ENDPOINT": sse_endpoint,
                },
            }
        }
    }

    return {
        "download_url": download_url,
        "config_example": config_example,
        "instructions": [
            {"step": 1, "text": "Download mcp-proxy.mjs and save to a permanent location"},
            {"step": 2, "text": "Generate a long-lived token in Home Assistant"},
            {"step": 3, "text": "Copy the config snippet below"},
            {"step": 4, "text": "Open claude_desktop_config.json (location varies by OS)"},
            {"step": 5, "text": "Paste and replace placeholders (<PATH_TO> and <TODO: your long-lived token>)"},
            {"step": 6, "text": "Restart Claude Desktop"},
        ],
        "config_paths": {
            "macos": "~/Library/Application Support/Claude/claude_desktop_config.json",
            "windows": "%APPDATA%\\Claude\\claude_desktop_config.json",
            "linux": "~/.config/Claude/claude_desktop_config.json",
        },
    }
