import subprocess
import time
import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from strands import Agent

MCP_PORT = 8931
MCP_URL  = f"http://127.0.0.1:{MCP_PORT}/mcp"

app = BedrockAgentCoreApp()

# ── start Playwright MCP once at container boot ──────────────────────────────
subprocess.Popen([
    "npx", "@playwright/mcp@latest",
    "--headless",
    "--port", str(MCP_PORT),
    "--host", "127.0.0.1",
])

for _ in range(30):
    try:
        requests.post(MCP_URL, json={}, timeout=1)
        break
    except Exception:
        time.sleep(0.5)

# ── cache tool specs once — schema doesn't change ────────────────────────────
def _base_transport():
    return streamablehttp_client(MCP_URL)

with MCPClient(_base_transport) as client:
    _tools = client.list_tools_sync()

# ── per-invocation handler ────────────────────────────────────────────────────
@app.entrypoint
async def invoke(payload, context):
    # extract JWT from inbound request — AgentCore already validated it
    token = context.request_headers.get("Authorization", "").removeprefix("Bearer ")

    def transport():
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return streamablehttp_client(MCP_URL, headers=headers)

    with MCPClient(transport) as client:
        agent = Agent(tools=_tools)
        result = agent(payload.get("prompt", ""))
        yield str(result)

if __name__ == "__main__":
    app.run()