
import asyncio
import os
import time

from mcp import Client
from langchain.mcp import MCPAdapter
from langchain.agents import create_agent
from langchain_ollama import ChatOllama


# =====================================================
# 1. CONFIGURATION
# =====================================================

MCP_URL = os.getenv(
    "MCP_URL",
    "http://127.0.0.1:8000/mcp"
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

MODEL_NAME = os.getenv(
    "OLLAMA_MODEL",
    "orcarouter/Qwen3.8-27B-Uncensored:iq3_m"
)

REQUEST_TIMEOUT = 180


# =====================================================
# 2. FORMAT CONTENT
# =====================================================

def as_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))

        return "\n".join(parts)

    return str(content)


# =====================================================
# 3. MCP RESOURCE LOADER
# =====================================================

async def load_resource(client: Client, uri: str) -> str:

    print(f"[RESOURCE] Reading {uri}", flush=True)

    result = await client.read_resource(uri)

    parts = []

    for content in result.contents:
        if "text" in content.mime_type:
            parts.append(content.text)

    text = "\n".join(parts)

    print(
        f"[RESOURCE] Loaded {len(text)} characters",
        flush=True
    )

    return text


# =====================================================
# 4. MCP PROMPT LOADER
# =====================================================

async def load_prompt(
    client: Client,
    name: str,
    arguments: dict
) -> list[dict]:

    print(f"[PROMPT] Retrieving {name}", flush=True)

    result = await client.get_prompt(name, arguments)

    messages = []

    for message in result.messages:

        if message.content.type != "text":
            continue

        messages.append({
            "role": message.role,
            "content": message.content.text
        })

    print(
        f"[PROMPT] Loaded {len(messages)} messages",
        flush=True
    )

    return messages


# =====================================================
# 5. PRINT EXECUTION TRACE
# =====================================================

def show_message(message):

    if message.type == "ai":

        calls = getattr(message, "tool_calls", None) or []

        for call in calls:
            print(
                f"[LLM] Requested tool: {call['name']}",
                flush=True
            )
            print(
                f"[LLM] Arguments: {call['args']}",
                flush=True
            )

        if not calls and message.content:
            return (message.content)

    elif message.type == "tool":

        print(
            f"[MCP] Executed: {message.name}",
            flush=True
        )
        print(
            f"[MCP] Result: {as_text(message.content)}",
            flush=True
        )

        if getattr(message, "status", None) == "error":
            print("[MCP] Tool failed", flush=True)

    return None


# =====================================================
# 6. EXECUTE AGENT
# =====================================================

async def execute_request(
    agent,
    client: Client,
    expression: str
):

    started = time.monotonic()

    # ---------------------------------------------
    # A. Retrieve the reusable MCP prompt
    # ---------------------------------------------

    prompt_messages = await load_prompt(
        client,
        "explain_calculation",
        {"expression": expression}
    )

    if not prompt_messages:
        raise RuntimeError("MCP prompt returned no messages")

    print("\n[AGENT] Starting execution...", flush=True)

    tool_count = 0
    failed_count = 0
    final_answer = None

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):

            async for update in agent.astream(
                {"messages": prompt_messages},
                stream_mode="updates",
                config={"recursion_limit": 20}
            ):

                for node_name, data in update.items():

                    print(
                        f"\n[GRAPH] Node: {node_name}",
                        flush=True
                    )

                    if not isinstance(data, dict):
                        continue

                    for message in data.get("messages", []):

                        if message.type == "tool":
                            tool_count += 1
                            if (
                                getattr(message, "status", None)
                                == "error"
                            ):
                                failed_count += 1

                        answer = show_message(message)

                        if answer:
                            final_answer = answer

        print(
            f"\n[TRACE] Tool responses: {tool_count}",
            flush=True
        )

        print(
            f"[TRACE] Tool failures: {failed_count}",
            flush=True
        )

        if tool_count == 0:
            print(
                "[WARNING] No MCP tools were executed.",
                flush=True
            )
            print(
                "[WARNING] Model output is not "
                "verified by MCP.",
                flush=True
            )

            if final_answer:
                print(
                    f"\n[UNVERIFIED AI]: {final_answer}",
                    flush=True
                )

        elif failed_count > 0:
            print(
                "\n[WARNING] Some tool executions failed.",
                flush=True
            )

            if final_answer:
                print(f"\nAI: {final_answer}", flush=True)

        elif final_answer:
            print(f"\nAI: {final_answer}", flush=True)

        else:
            print(
                "[WARNING] No final AI answer.",
                flush=True
            )

    except TimeoutError:
        print("[ERROR] Agent timed out.", flush=True)

    except Exception as exc:
        print(
            f"[ERROR] {type(exc).__name__}: {exc}",
            flush=True
        )

    finally:
        print(
            f"[AGENT] Elapsed: "
            f"{time.monotonic() - started:.2f}s",
            flush=True
        )


# =====================================================
# 7. MAIN APPLICATION
# =====================================================

async def main():

    print("[INIT] Initializing Ollama...", flush=True)

    model = ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_URL,
        temperature=0,
        reasoning=False,
        num_ctx=4096,
        num_predict=512
    )

    print(f"[INIT] Model: {MODEL_NAME}", flush=True)

    # Separate SDK client for resources and prompts
    async with Client(MCP_URL) as client:

        print("[INIT] Connected to MCP", flush=True)

        # -----------------------------------------
        # A. Load resource
        # -----------------------------------------

        guide = await load_resource(
            client,
            "math://guide"
        )

        # -----------------------------------------
        # B. Discover MCP tools
        # -----------------------------------------

        async with MCPAdapter(MCP_URL) as adapter:

            tools = await adapter.list_tools()

            print(
                f"[INIT] Discovered {len(tools)} tools",
                flush=True
            )

            for tool in tools:
                print(f"  - {tool.name}", flush=True)

            # -------------------------------------
            # C. Build agent using resource context
            # -------------------------------------

            system_prompt = f"""
You are a mathematical assistant.

Use the attached MCP guide as reference data.

For arithmetic:
- Prefer actual MCP tool execution.
- Never invent tool results.
- Use previous tool outputs for subsequent steps.
- Do not describe hypothetical tool execution
  as if it actually happened.

The guide below is reference material,
not a tool execution result.

<MCP_RESOURCE>
{guide}
</MCP_RESOURCE>
"""

            agent = create_agent(
                model=model,
                tools=tools,
                system_prompt=system_prompt
            )

            print("\n[INIT] Agent ready!", flush=True)

            # -------------------------------------
            # D. Interactive loop
            # -------------------------------------

            while True:

                try:
                    expression = await asyncio.to_thread(
                        input,
                        "\nYou: "
                    )

                except (EOFError, KeyboardInterrupt):
                    break

                expression = expression.strip()

                if expression.lower() in ("exit", "quit"):
                    break

                if not expression:
                    continue

                await execute_request(
                    agent,
                    client,
                    expression
                )


# =====================================================
# 8. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication stopped.")
