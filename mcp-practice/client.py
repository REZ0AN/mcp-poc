
import asyncio
import json

from mcp import Client


# =====================================================
# 1. CONFIGURATION
# =====================================================

MCP_URL = "http://127.0.0.1:8000/mcp"


# =====================================================
# 2. HELPER FUNCTIONS
# =====================================================

def print_result(result):
    """Display an MCP tool execution result."""

    print("Is Error:", result.is_error)

    # Structured output, if provided by the server
    if result.structured_content is not None:
        print(
            "Structured Content:",
            json.dumps(
                result.structured_content,
                indent=2
            )
        )

    # Content blocks, including text responses
    for content in result.content:
        if content.type == "text":
            print("Text:", content.text)
        else:
            print("Content:", content)


async def execute_tool(
    client: Client,
    name: str,
    arguments: dict
):
    """Execute a tool and display its result."""

    print(f"\n=== EXECUTE: {name} ===")

    try:
        result = await client.call_tool(
            name,
            arguments
        )

        print_result(result)
        return result

    except Exception as exc:
        print(
            f"Failed to execute '{name}': "
            f"{type(exc).__name__}: {exc}"
        )
        return None


# =====================================================
# 3. MCP CLIENT APPLICATION
# =====================================================

async def main():

    async with Client(MCP_URL) as client:

        # ============================================
        # 1. SERVER INFORMATION
        # ============================================

        print("=== SERVER ===")
        print("Protocol:", client.protocol_version)

        if client.server_info:
            print("Name:", client.server_info.name)
            print("Version:", client.server_info.version)

        # ============================================
        # 2. TOOL DISCOVERY
        # ============================================

        print("\n=== AVAILABLE TOOLS ===")

        response = await client.list_tools()

        for tool in response.tools:
            print(f"\nName: {tool.name}")
            print(f"Description: {tool.description}")

            print(
                "Input Schema:",
                json.dumps(
                    tool.input_schema,
                    indent=2
                )
            )

            # Optional output schema
            if tool.output_schema is not None:
                print(
                    "Output Schema:",
                    json.dumps(
                        tool.output_schema,
                        indent=2
                    )
                )

        # ============================================
        # 3. EXECUTE ADD
        # ============================================

        await execute_tool(
            client,
            "add",
            {"a": 10, "b": 20}
        )

        # ============================================
        # 4. EXECUTE SUBTRACT
        # ============================================

        await execute_tool(
            client,
            "subtract",
            {"a": 20, "b": 8}
        )

        # ============================================
        # 5. EXECUTE MULTIPLY
        # ============================================

        await execute_tool(
            client,
            "multiply",
            {"a": 5, "b": 6}
        )

        # ============================================
        # 6. EXECUTE DIVIDE
        # ============================================

        await execute_tool(
            client,
            "divide",
            {"a": 20, "b": 4}
        )

        # ============================================
        # 7. EXECUTE POWER
        # ============================================
        await execute_tool(
            client,
            "power",
            {"a": 2, "b": 3}
        )
        # ============================================
        # 7. TEST BUSINESS ERROR
        # ============================================

        await execute_tool(
            client,
            "divide",
            {"a": 10, "b": 0}
        )

        # ============================================
        # 8. TEST UNKNOWN TOOL
        # ============================================

        await execute_tool(
            client,
            "unknown_tool",
            {"a": 10, "b": 5}
        )


# =====================================================
# 4. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    asyncio.run(main())
