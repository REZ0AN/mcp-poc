
import asyncio
import os
import time

from mcp import Client
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_ollama import ChatOllama


# =====================================================
# 1. CONFIGURATION
# =====================================================

MATH_URL = "http://127.0.0.1:8000/mcp"
DOCS_URL = "http://127.0.0.1:8001/mcp"

MODEL_NAME = os.getenv(
    "OLLAMA_MODEL",
    "orcarouter/Qwen3.8-27B-Uncensored:iq3_m"
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

REQUEST_TIMEOUT = 180

SERVER_URLS = {
    "math": MATH_URL,
    "docs": DOCS_URL
}


# =====================================================
# 2. SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a project assistant with MCP tools.

Tools are provided by two independent servers:

1. Math server:
   Arithmetic operations.

2. Documents server:
   Searching and reading project documents.

Rules:
- Use document tools to retrieve project information.
- Do not invent document content or financial values.
- Use math tools for arithmetic calculations.
- For multi-step operations, use actual prior tool results.
- Do not narrate hypothetical tool calls.
- Never claim to have accessed a document unless
  a document tool returned it.
- Clearly identify missing information.
- Answer concisely after completing the task.
"""


# =====================================================
# 3. SERVER AVAILABILITY CHECK
# =====================================================

async def check_server(name: str, url: str) -> bool:
    """
    Connect using the official MCP Client.

    A successful connection and tools/list response
    demonstrate that the server is reachable.
    """

    try:
        async with asyncio.timeout(8):
            async with Client(url) as client:
                response = await client.list_tools()

                print(
                    f"[SERVER] {name}: ONLINE "
                    f"({len(response.tools)} tools)",
                    flush=True
                )
                return True

    except Exception as exc:
        print(
            f"[SERVER] {name}: UNAVAILABLE "
            f"({type(exc).__name__})",
            flush=True
        )
        return False


async def discover_available_servers():
    """
    For this read-only local exercise, omit servers
    that fail discovery.

    The adapter will connect again when initialized.
    """

    healthy = {}

    for name, url in SERVER_URLS.items():
        if await check_server(name, url):
            healthy[name] = {"url": url}

    return {
        "mcpServers": healthy
    }


# =====================================================
# 4. OUTPUT FORMATTER
# =====================================================

def format_content(content):

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for block in content:
            if isinstance(block, str):
                parts.append(block)

            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(
                        block.get("text", "")
                    )

        return "\n".join(parts)

    return str(content)


# =====================================================
# 5. EXECUTION TRACE
# =====================================================

def print_message(message):

    if message.type == "ai":

        tool_calls = (
            getattr(message, "tool_calls", None)
            or []
        )

        for call in tool_calls:
            print(
                f"[LLM] Tool requested: "
                f"{call['name']}",
                flush=True
            )
            print(
                f"[LLM] Arguments: "
                f"{call['args']}",
                flush=True
            )

        if not tool_calls and message.content:
            return format_content(message.content)

    elif message.type == "tool":

        print(
            f"[MCP] Tool executed: "
            f"{message.name}",
            flush=True
        )

        print(
            f"[MCP] Result: "
            f"{format_content(message.content)}",
            flush=True
        )

        if getattr(message, "status", None) == "error":
            print(
                "[MCP] Tool returned an error",
                flush=True
            )

    return None


# =====================================================
# 6. EXECUTE AGENT
# =====================================================

async def execute_prompt(agent, prompt: str):

    started = time.monotonic()

    print(
        "\n[AGENT] Starting...",
        flush=True
    )

    final_answer = None
    tool_count = 0
    failed_tools = 0

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):

            async for update in agent.astream(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                },
                stream_mode="updates",
                config={"recursion_limit": 20}
            ):

                for node_name, data in update.items():

                    print(
                        f"\n[GRAPH] {node_name}",
                        flush=True
                    )

                    if not isinstance(data, dict):
                        continue

                    for message in data.get("messages", []):

                        if message.type == "tool":
                            tool_count += 1

                            if (
                                getattr(
                                    message,
                                    "status",
                                    None
                                ) == "error"
                            ):
                                failed_tools += 1

                        answer = print_message(message)

                        if answer is not None:
                            final_answer = answer

        print(
            f"\n[TRACE] Tool responses: {tool_count}",
            flush=True
        )
        print(
            f"[TRACE] Tool failures: {failed_tools}",
            flush=True
        )

        if tool_count == 0:
            print(
                "[WARNING] No tools were executed.",
                flush=True
            )

        if final_answer:
            label = (
                "AI"
                if tool_count > 0 and failed_tools == 0
                else "AI (not fully tool-verified)"
            )

            print(
                f"\n{label}: {final_answer}",
                flush=True
            )

        else:
            print(
                "\n[WARNING] No final AI response.",
                flush=True
            )

    except TimeoutError:
        print(
            "\n[ERROR] Agent timed out.",
            flush=True
        )

    except Exception as exc:
        print(
            f"\n[ERROR] {type(exc).__name__}: {exc}",
            flush=True
        )

    finally:
        print(
            f"\n[AGENT] Elapsed: "
            f"{time.monotonic() - started:.2f}s",
            flush=True
        )


# =====================================================
# 7. MAIN APPLICATION
# =====================================================

async def main():

    print("[INIT] Checking MCP servers...")

    config = await discover_available_servers()

    if not config["mcpServers"]:
        raise RuntimeError(
            "No MCP servers are available"
        )

    print("\n[INIT] Connecting MCPAdapter...")

    async with MCPAdapter(config) as adapter:

        tools = await adapter.list_tools()

        if not tools:
            raise RuntimeError(
                "No tools discovered"
            )

        print(
            f"\n[INIT] Discovered {len(tools)} tools:"
        )

        for tool in tools:
            print(
                f"  - {tool.name}: "
                f"{tool.description}"
            )

        model = ChatOllama(
            model=MODEL_NAME,
            base_url=OLLAMA_URL,
            temperature=0,
            reasoning=False,
            num_ctx=4096,
            num_predict=512
        )

        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT
        )

        print("\n[INIT] Multi-server agent ready!")

        while True:

            try:
                prompt = await asyncio.to_thread(
                    input,
                    "\nYou: "
                )

            except (EOFError, KeyboardInterrupt):
                break

            prompt = prompt.strip()

            if prompt.lower() in ("exit", "quit"):
                break

            if not prompt:
                continue

            await execute_prompt(agent, prompt)


# =====================================================
# 8. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nStopped.")
