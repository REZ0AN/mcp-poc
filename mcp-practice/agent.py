
import asyncio
import os
import re
import time

from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
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

REQUEST_TIMEOUT = 120
MAX_ATTEMPTS = 2


# =====================================================
# 2. SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are a mathematical assistant that uses MCP tools.

The available tools perform arithmetic operations.

Rules:
1. Call tools for every arithmetic operation.
2. Never calculate arithmetic mentally.
3. Never write a simulated tool execution.
4. Do not describe tool calls in plain text.
5. Generate structured tool calls instead.
6. For multi-step calculations, call tools sequentially.
7. Use actual tool results for subsequent operations.
8. Provide a final answer only after the necessary
   tool calls have completed successfully.

Example:
User: Multiply 25 by 8, then subtract 40.

Action 1: Call multiply(a=25, b=8).
Read the tool result.

Action 2: Call subtract(a=200, b=40).
Read the tool result.

Final response: The answer is 160.
"""


# =====================================================
# 3. CONTENT FORMATTING
# =====================================================

def format_content(content):
    """Convert LangChain message content into text."""

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
# 4. ESTIMATE REQUIRED TOOL OPERATIONS
# =====================================================

def estimate_required_tools(prompt: str) -> int:
    """
    Simple exercise-only heuristic.

    Count distinct arithmetic operation types in
    the user prompt.

    This is NOT a general expression parser.
    """

    patterns = [
        r"\b(add|plus|sum)\b",
        r"\b(subtract|minus)\b",
        r"\b(multiply|multiplied|times)\b",
        r"\b(divide|divided)\b",
        r"\b(power|raise|raised)\b",
    ]

    matches = sum(
        bool(re.search(pattern, prompt, re.I))
        for pattern in patterns
    )

    return max(1, matches)


# =====================================================
# 5. EXECUTE AGENT AND COLLECT TRACES
# =====================================================

async def run_agent_once(agent, prompt: str):
    """
    Run one LangGraph agent invocation.

    Collect only tool calls actually returned by
    the model and tool results actually executed.
    """

    requested_calls = []
    executed_calls = []
    failed_calls = []
    final_answer = None

    async for update in agent.astream(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        config={"recursion_limit": 20},
        stream_mode="updates"
    ):

        for node_name, data in update.items():

            print(
                f"\n[GRAPH] Node: {node_name}",
                flush=True
            )

            if not isinstance(data, dict):
                continue

            messages = data.get("messages", [])

            for message in messages:

                # ---------------------------------
                # MODEL MESSAGE
                # ---------------------------------

                if message.type == "ai":

                    calls = (
                        getattr(message, "tool_calls", None)
                        or []
                    )

                    for call in calls:

                        requested_calls.append(call)

                        print(
                            f"[LLM] Requested: {call['name']}",
                            flush=True
                        )

                        print(
                            f"[LLM] Arguments: {call['args']}",
                            flush=True
                        )

                    if not calls and message.content:
                        final_answer = format_content(
                            message.content
                        )

                # ---------------------------------
                # ACTUAL TOOL RESPONSE
                # ---------------------------------

                elif message.type == "tool":

                    tool_result = {
                        "name": message.name,
                        "content": format_content(
                            message.content
                        ),
                        "status": getattr(
                            message,
                            "status",
                            "success"
                        )
                    }

                    print(
                        f"[MCP] Executed: {message.name}",
                        flush=True
                    )

                    print(
                        f"[MCP] Result: "
                        f"{tool_result['content']}",
                        flush=True
                    )

                    if tool_result["status"] == "error":
                        failed_calls.append(tool_result)

                        print(
                            "[MCP] Execution failed",
                            flush=True
                        )

                    else:
                        executed_calls.append(tool_result)

    return {
        "requested_calls": requested_calls,
        "executed_calls": executed_calls,
        "failed_calls": failed_calls,
        "final_answer": final_answer
    }


# =====================================================
# 6. EXECUTE PROMPT WITH RETRY POLICY
# =====================================================

async def execute_prompt(agent, prompt: str):

    started = time.monotonic()

    required_tools = estimate_required_tools(prompt)

    print(
        "\n[AGENT] Starting request...",
        flush=True
    )

    print(
        f"[POLICY] Expected minimum tool calls: "
        f"{required_tools}",
        flush=True
    )

    attempt_prompt = prompt

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):

            for attempt in range(1, MAX_ATTEMPTS + 1):

                print(
                    f"\n[AGENT] Attempt "
                    f"{attempt}/{MAX_ATTEMPTS}",
                    flush=True
                )

                result = await run_agent_once(
                    agent,
                    attempt_prompt
                )

                successful = len(
                    result["executed_calls"]
                )

                failed = len(
                    result["failed_calls"]
                )

                print(
                    f"\n[TRACE] Successful tools: "
                    f"{successful}",
                    flush=True
                )

                print(
                    f"[TRACE] Failed tools: {failed}",
                    flush=True
                )

                # ---------------------------------
                # VERIFIED ENOUGH FOR THIS EXERCISE
                # ---------------------------------

                if (
                    successful >= required_tools
                    and failed == 0
                ):

                    if result["final_answer"]:
                        print(
                            "\nAI: "
                            + result["final_answer"],
                            flush=True
                        )
                    else:
                        print(
                            "\n[WARNING] Tool calls completed "
                            "but no final AI response.",
                            flush=True
                        )

                    return

                # ---------------------------------
                # TOOL EXECUTION ERROR
                # ---------------------------------

                if failed > 0:

                    print(
                        "\n[ERROR] A tool failed. "
                        "Review its MCP result.",
                        flush=True
                    )
                    return

                # ---------------------------------
                # RETRY WITHOUT ACCEPTING ANSWER
                # ---------------------------------

                if attempt < MAX_ATTEMPTS:

                    print(
                        "\n[POLICY] Tool execution "
                        "requirements not met.",
                        flush=True
                    )

                    print(
                        "[POLICY] Retrying with "
                        "explicit tool instructions...",
                        flush=True
                    )

                    attempt_prompt = (
                        "You must use the available "
                        "MCP tools to complete this task.\n"
                        "Do not calculate manually.\n"
                        "Do not narrate hypothetical "
                        "tool executions.\n"
                        "Emit actual structured tool calls.\n"
                        "Complete every operation using "
                        "the preceding tool result.\n"
                        f"Task: {prompt}"
                    )

                else:

                    print(
                        "\n[ERROR] The agent did not "
                        "complete the required MCP "
                        "tool executions.",
                        flush=True
                    )

                    print(
                        "[ERROR] The generated answer "
                        "has been withheld.",
                        flush=True
                    )

    except TimeoutError:

        print(
            "\n[ERROR] Agent timed out.",
            flush=True
        )

    except Exception as exc:

        print(
            f"\n[ERROR] {type(exc).__name__}: "
            f"{exc}",
            flush=True
        )

    finally:

        elapsed = time.monotonic() - started

        print(
            f"\n[AGENT] Elapsed: {elapsed:.2f}s",
            flush=True
        )


# =====================================================
# 7. MAIN
# =====================================================

async def main():

    print("[INIT] Initializing Ollama...", flush=True)

    model = ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_URL,
        temperature=0,

        # Disable Qwen3 thinking mode.
        # Useful for short, tool-oriented tasks.
        reasoning=False,

        # Bound response length.
        num_predict=512,
    )

    print(
        f"[INIT] Model: {MODEL_NAME}",
        flush=True
    )

    print(
        "[INIT] Connecting to MCP...",
        flush=True
    )

    async with MCPAdapter(MCP_URL) as adapter:

        tools = await adapter.list_tools()

        if not tools:
            raise RuntimeError(
                "No MCP tools discovered."
            )

        print(
            f"\n[INIT] Discovered {len(tools)} tools:"
        )

        for tool in tools:
            print(
                f"  - {tool.name}: {tool.description}"
            )

        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT
        )

        print(
            "\n[INIT] Agent ready!",
            flush=True
        )

        print(
            "[INIT] Type 'exit' to quit.",
            flush=True
        )

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

    print("\nApplication stopped.")


# =====================================================
# 8. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nStopped.")
