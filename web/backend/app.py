"""
project-vault web chat UI — backend (v0)

A second, independent MCP *client* for project-vault, proving the server
isn't Claude-Code-specific. This is a small FastAPI app that:

  - talks to the Anthropic Messages API directly (not through Claude Code)
  - talks to `src/server.py` over MCP (stdio), the same way Claude Code does
  - runs the tool-use loop itself: model asks for a tool call, we call it
    against the live MCP session, feed the result back, repeat until the
    model returns plain text

Nothing about the vault or server.py changes for this — the whole point is
that a brand new client can reach it with no server-side changes.

Run from the repo root:
    uvicorn web.backend.app:app --reload --port 8000
"""

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("project-vault-web")

REPO_ROOT = Path(__file__).parent.parent.parent
SERVER_SCRIPT = REPO_ROOT / "src" / "server.py"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

MODEL = "claude-haiku-4-5-20251001"

anthropic_client = AsyncAnthropic()

# Populated at startup: the live MCP session and its tools, converted to
# Anthropic's tool schema. Global and single-session by design for v0 — see
# the plan/CLAUDE.md for why (one local user, one browser tab, no auth yet).
mcp_session: ClientSession | None = None
anthropic_tools: list[dict] = []
conversation: list[dict] = []


def _mcp_tool_to_anthropic(tool) -> dict:
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp_session, anthropic_tools

    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(
            stdio_client(
                StdioServerParameters(command="python", args=[str(SERVER_SCRIPT)])
            )
        )
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        tools_result = await session.list_tools()
        mcp_session = session
        anthropic_tools = [_mcp_tool_to_anthropic(t) for t in tools_result.tools]

        logger.info(
            "MCP session ready — %d tool(s): %s",
            len(anthropic_tools),
            ", ".join(t["name"] for t in anthropic_tools),
        )

        yield

        logger.info("shutting down MCP session")


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


def _tool_result_to_text(result) -> str:
    parts = [block.text for block in result.content if block.type == "text"]
    text = "\n".join(parts)
    if result.is_error:
        return f"Error: {text}"
    return text


@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    assert mcp_session is not None, "MCP session not initialized"

    logger.info("user: %s", req.message)
    conversation.append({"role": "user", "content": req.message})

    turn = 0
    while True:
        turn += 1
        response = await anthropic_client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=anthropic_tools,
            messages=conversation,
        )
        conversation.append({"role": "assistant", "content": response.content})
        logger.info(
            "model turn %d — stop_reason=%s, usage=%s",
            turn,
            response.stop_reason,
            response.usage,
        )

        if response.stop_reason != "tool_use":
            reply = "".join(
                block.text for block in response.content if block.type == "text"
            )
            logger.info("assistant: %s", reply)
            return ChatResponse(reply=reply)

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            logger.info("tool_use: %s(%s)", block.name, block.input)
            result = await mcp_session.call_tool(block.name, block.input)
            result_text = _tool_result_to_text(result)
            logger.info(
                "tool_result: %s -> %s",
                block.name,
                result_text[:200] + ("..." if len(result_text) > 200 else ""),
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                }
            )
        conversation.append({"role": "user", "content": tool_results})


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
