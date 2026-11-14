
import asyncio
import json

from mcp import Client


# =====================================================
# 1. CONFIGURATION
# =====================================================

MCP_URL = "http://127.0.0.1:8000/mcp"


# =====================================================
# 2. OUTPUT HELPERS
# =====================================================

def heading(title: str):
    print("\n" + "=" * 55)
    print(title)
    print("=" * 55)


def print_resource(result):

    for content in result.contents:

        print("URI:", content.uri)
        print("MIME:", content.mime_type)
        print("Content:", content.text)


def print_prompt(result):

    for message in result.messages:

        print("Role:", message.role)

        if message.content.type == "text":
            print("Content:")
            print(message.content.text)
        else:
            print("Content:", message.content)


def print_tool_result(result):

    print("Is Error:", result.is_error)

    if result.structured_content is not None:
        print(
            "Structured Content:",
            json.dumps(
                result.structured_content,
                indent=2
            )
        )

    for block in result.content:

        if block.type == "text":
            print("Tool Output:", block.text)
        else:
            print("Other content:", block)


# =====================================================
# 3. DISCOVER SERVER CAPABILITIES
# =====================================================

async def inspect_server(client):

    heading("SERVER INFORMATION")

    print("Protocol:", client.protocol_version)

    if client.server_info:
        print("Name:", client.server_info.name)
        print("Version:", client.server_info.version)

    if client.server_capabilities:
        print(
            "Capabilities:",
            client.server_capabilities.model_dump(
                exclude_none=True
            )
        )


# =====================================================
# 4. TOOL DISCOVERY AND EXECUTION
# =====================================================

async def test_tools(client):

    heading("DISCOVER TOOLS")

    response = await client.list_tools()

    for tool in response.tools:

        print("\nName:", tool.name)
        print("Description:", tool.description)

        print(
            "Input Schema:",
            json.dumps(
                tool.input_schema,
                indent=2
            )
        )

    heading("EXECUTE TOOLS")

    test_cases = [
        ("add", {"a": 4, "b": 6}),
        ("subtract", {"a": 20, "b": 8}),
        ("multiply", {"a": 10, "b": 5}),
        ("divide", {"a": 20, "b": 4}),
        ("power", {"a": 2, "b": 10}),
    ]

    for name, arguments in test_cases:

        print(f"\nCalling tool: {name}")
        print("Arguments:", arguments)

        result = await client.call_tool(
            name,
            arguments
        )

        print_tool_result(result)


# =====================================================
# 5. STATIC RESOURCE DISCOVERY
# =====================================================

async def test_static_resource(client):

    heading("DISCOVER STATIC RESOURCES")

    response = await client.list_resources()
    for resource in response.resources:

        print("Name:", resource.name)
        print("URI:", resource.uri)
        print("MIME:", resource.mime_type)

    heading("READ STATIC RESOURCE")

    result = await client.read_resource(
        "math://guide"
    )
    print_resource(result)


# =====================================================
# 6. DYNAMIC RESOURCE TEMPLATE
# =====================================================

async def test_resource_template(client):

    heading("DISCOVER RESOURCE TEMPLATES")

    response = await client.list_resource_templates()

    for template in response.resource_templates:

        print("Name:", template.name)
        print("URI Template:", template.uri_template)
        print("MIME:", template.mime_type)

    heading("READ DYNAMIC RESOURCE")

    result = await client.read_resource(
        "math://operations/multiply"
    )

    print_resource(result)

    heading("READ POWER DOCUMENTATION")

    result = await client.read_resource(
        "math://operations/power"
    )

    print_resource(result)


# =====================================================
# 7. PROMPT DISCOVERY AND RETRIEVAL
# =====================================================

async def test_prompts(client):

    heading("DISCOVER PROMPTS")

    response = await client.list_prompts()

    for prompt in response.prompts:

        print("\nName:", prompt.name)
        print("Description:", prompt.description)

        for argument in prompt.arguments or []:

            print(
                f"Argument: {argument.name}, "
                f"Required: {argument.required}"
            )

    heading("GET EXPLAIN CALCULATION PROMPT")

    result = await client.get_prompt(
        "explain_calculation",
        {
            "expression":
                "(4 + 6) * 10"
        }
    )

    print_prompt(result)

    heading("GET TEACH OPERATION PROMPT")

    result = await client.get_prompt(
        "teach_operation",
        {
            "operation": "multiplication"
        }
    )

    print_prompt(result)


# =====================================================
# 8. ERROR HANDLING EXERCISE
# =====================================================

async def test_errors(client):

    heading("ERROR HANDLING")

    # Tool execution error
    result = await client.call_tool(
        "divide",
        {
            "a": 10,
            "b": 0
        }
    )

    print("\nDivide by zero:")
    print_tool_result(result)

    # Unknown resource
    try:
        await client.read_resource(
            "math://operations/unknown"
        )

    except Exception as error:

        print("\nUnknown resource error:")
        print(type(error).__name__)
        print(str(error))


# =====================================================
# 9. MAIN
# =====================================================

async def main():

    async with Client(MCP_URL) as client:

        await inspect_server(client)

        await test_tools(client)

        await test_static_resource(client)

        await test_resource_template(client)

        await test_prompts(client)

        await test_errors(client)

        heading("ALL TESTS COMPLETED")


# =====================================================
# 10. ENTRY POINT
# =====================================================

if __name__ == "__main__":
    asyncio.run(main())
