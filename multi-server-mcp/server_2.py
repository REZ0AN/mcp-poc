
import logging
import math

from mcp.server import MCPServer


# =====================================================
# 1. CONFIGURATION
# =====================================================

HOST = "127.0.0.1"
PORT = 8000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("math-mcp-server")


# =====================================================
# 2. BUSINESS SERVICE
# =====================================================

class MathService:

    @staticmethod
    def add(a: float, b: float) -> float:
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def power(a: float, b: float) -> float:
        result = a ** b

        if isinstance(result, complex):
            raise ValueError("Complex results are not supported")

        return float(result)


# =====================================================
# 3. INITIALIZE MCP SERVER
# =====================================================

mcp = MCPServer(
    "Math MCP Server",
    version="1.0.0",
    instructions=(
        "Provides mathematical tools, documentation "
        "resources, and reusable teaching prompts."
    )
)


# =====================================================
# 4. COMMON VALIDATION
# =====================================================

def validate_numbers(a: float, b: float):

    if not (
        math.isfinite(a)
        and math.isfinite(b)
    ):
        raise ValueError("Numbers must be finite")


# =====================================================
# 5. MCP TOOLS
# =====================================================

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    validate_numbers(a, b)
    return MathService.add(a, b)


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    validate_numbers(a, b)
    return MathService.subtract(a, b)


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    validate_numbers(a, b)
    return MathService.multiply(a, b)


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b. The denominator must be nonzero."""
    validate_numbers(a, b)
    return MathService.divide(a, b)


@mcp.tool()
def power(a: float, b: float) -> float:
    """Raise a to the power of b."""
    validate_numbers(a, b)

    result = MathService.power(a, b)

    if not math.isfinite(result):
        raise ValueError("Result is not finite")

    return result


# =====================================================
# 6. STATIC MCP RESOURCE
# =====================================================

@mcp.resource(
    "math://guide",
    mime_type="text/markdown"
)
def math_guide() -> str:
    """General math server documentation."""

    return """
# Math MCP Server

This server supports five mathematical operations.

## Available Operations

1. add(a, b)
   Adds two numbers.

2. subtract(a, b)
   Subtracts b from a.

3. multiply(a, b)
   Multiplies two numbers.

4. divide(a, b)
   Divides a by b.

5. power(a, b)
   Raises a to the power b.

## Rules

- Division by zero is prohibited.
- All numeric inputs must be finite.
- Complex results are not supported.
- Multi-step calculations should follow
  their mathematical order.

## Example

Expression:

(4 + 6) * 10

Steps:

1. add(4, 6) = 10
2. multiply(10, 10) = 100

Result: 100
"""


# =====================================================
# 7. DYNAMIC RESOURCE TEMPLATE
# =====================================================

OPERATION_DOCS = {
    "add": {
        "description": "Combines two numbers.",
        "example": "add(4, 6) = 10",
    },
    "subtract": {
        "description": "Subtracts one number from another.",
        "example": "subtract(10, 4) = 6",
    },
    "multiply": {
        "description": "Calculates the product of two numbers.",
        "example": "multiply(5, 10) = 50",
    },
    "divide": {
        "description": "Divides one number by another.",
        "example": "divide(20, 4) = 5",
    },
    "power": {
        "description": "Raises a base to an exponent.",
        "example": "power(2, 3) = 8",
    },
}


@mcp.resource(
    "math://operations/{operation}",
    mime_type="text/plain"
)
def operation_documentation(operation: str) -> str:
    """Documentation for a specific math operation."""

    data = OPERATION_DOCS.get(operation)

    if data is None:
        raise ValueError(
            f"Unknown operation: {operation}"
        )

    return (
        f"Operation: {operation}\n"
        f"Description: {data['description']}\n"
        f"Example: {data['example']}"
    )


# =====================================================
# 8. MCP PROMPTS
# =====================================================

@mcp.prompt()
def explain_calculation(expression: str) -> str:
    """Explain a mathematical calculation step by step."""

    return f"""
You are a mathematical assistant.

Explain the following expression:

{expression}

Instructions:
1. Identify the mathematical operations.
2. Explain their order.
3. Use available calculation tools when possible.
4. Do not invent tool execution results.
5. Explain the final result in simple English.
"""


@mcp.prompt()
def teach_operation(operation: str) -> str:
    """Teach a mathematical operation."""

    return f"""
You are a mathematics teacher.

Teach the following operation:

{operation}

Include:
1. Definition
2. How the operation works
3. A simple example
4. Common mistakes
5. Two practice problems

Use simple English.
"""


# =====================================================
# 9. APPLICATION ENTRY POINT
# =====================================================

if __name__ == "__main__":

    logger.info(
        "Starting MCP server at http://%s:%d/mcp",
        HOST,
        PORT
    )

    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        stateless_http=True,
        json_response=True,
        max_request_body_size=1024 * 1024
    )
