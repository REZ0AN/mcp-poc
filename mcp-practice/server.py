
import logging
import math

from mcp.server import MCPServer
from math_service import MathService


# =====================================================
# 1. LOGGING
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("math-mcp-server")


# =====================================================
# 2. MCP SERVER
# =====================================================

mcp = MCPServer(
    "Math MCP Server",
    version="1.0.0",
    instructions="Tools for basic arithmetic operations."
)


# =====================================================
# 3. INPUT VALIDATION
# =====================================================

def validate_numbers(a: float, b: float):
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("Numbers must be finite")


# =====================================================
# 4. MCP TOOL REGISTRATION
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
    return MathService.power(a, b)

# =====================================================
# 5. APPLICATION ENTRY POINT
# =====================================================

if __name__ == "__main__":

    logger.info("Starting Math MCP Server")

    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8000,
        stateless_http=True,
        json_response=True,
        max_request_body_size=1024 * 1024
    )
