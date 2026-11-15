
import asyncio
import sys
import json

import httpx2

from mcp import Client
from mcp.client.streamable_http import (
    streamable_http_client,
)


# =====================================================
# 1. CONFIGURATION
# =====================================================

MCP_URL = "http://127.0.0.1:8000/mcp"

# Usage:
# uv run python auth_client.py alice
# uv run python auth_client.py bob

TOKENS = {
    "alice": "alice-token",
    "bob": "bob-token",
}


# =====================================================
# 2. OUTPUT HELPERS
# =====================================================

def show_tool_result(result):

    print("Is Error:", result.is_error)

    if result.structured_content is not None:
        print(
            "Structured result:",
            json.dumps(
                result.structured_content,
                indent=2,
            ),
        )

    for block in result.content:
        if block.type == "text":
            print("Text:", block.text)


def show_resource(result):

    for block in result.contents:
        if "text" in block.mime_type:
            print(block.text)


# =====================================================
# 3. AUTHENTICATED CLIENT
# =====================================================

async def main():

    identity = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "alice"
    )

    token = TOKENS.get(identity)

    if token is None:
        raise ValueError(
            "Use 'alice' or 'bob'"
        )

    print(
        f"[CLIENT] Identity: {identity}",
        flush=True,
    )

    # HTTP client sends authorization on requests.
    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}"
        },
        timeout=httpx2.Timeout(
            30.0,
            read=300.0,
        ),
    ) as http_client:

        transport = streamable_http_client(
            MCP_URL,
            http_client=http_client,
        )

        async with Client(transport) as client:

            # -------------------------------------
            # 1. DISCOVER TOOLS
            # -------------------------------------

            print("\n=== DISCOVER TOOLS ===")

            tools = await client.list_tools()

            for tool in tools.tools:
                print("-", tool.name)

            # -------------------------------------
            # 2. AUTHENTICATED IDENTITY
            # -------------------------------------

            print("\n=== WHO AM I? ===")

            identity_result = (
                await client.call_tool(
                    "whoami",
                    {},
                )
            )

            show_tool_result(identity_result)

            # -------------------------------------
            # 3. READ RESOURCE
            # -------------------------------------

            print("\n=== READ RESOURCE ===")

            resource = await client.read_resource(
                "math://guide"
            )

            show_resource(resource)

            # -------------------------------------
            # 4. GET PROMPT
            # -------------------------------------

            print("\n=== GET PROMPT ===")

            prompt = await client.get_prompt(
                "explain_calculation",
                {
                    "expression": "4 + 6"
                },
            )

            for message in prompt.messages:
                if message.content.type == "text":
                    print(message.content.text)

            # -------------------------------------
            # 5. EXECUTE PROTECTED TOOL
            # -------------------------------------

            print("\n=== EXECUTE ADD ===")

            result = await client.call_tool(
                "add",
                {
                    "a": 4,
                    "b": 6,
                },
            )

            show_tool_result(result)


# =====================================================
# 4. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(
            f"[ERROR] {type(exc).__name__}: {exc}"
        )
        raise
