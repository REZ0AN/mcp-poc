
import logging
import math

from pydantic import AnyHttpUrl
from mcp.server import MCPServer
from mcp.server.auth.provider import (
    AccessToken,
    TokenVerifier,
)
from mcp.server.auth.settings import AuthSettings
from mcp.server.auth.middleware.auth_context import (
    get_access_token,
)


# =====================================================
# 1. CONFIGURATION
# =====================================================

HOST = "127.0.0.1"
PORT = 8000
RESOURCE_URL = f"http://{HOST}:{PORT}/mcp"

# Only for this local exercise.
# There is no real OAuth issuer at this address.
DEMO_ISSUER = "https://auth.example.com"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("secured-math-mcp")


# =====================================================
# 2. DEMO ACCESS TOKENS
# =====================================================

# Never store real access tokens in source code.
# These are fixed, local demonstration credentials.

KNOWN_TOKENS = {
    "alice-token": AccessToken(
        token="alice-token",
        client_id="alice",
        scopes=["math:read", "math:execute"],
        resource=RESOURCE_URL,
    ),
    "bob-token": AccessToken(
        token="bob-token",
        client_id="bob",
        scopes=["math:read"],
        resource=RESOURCE_URL,
    ),
}


# =====================================================
# 3. TOKEN VERIFIER
# =====================================================

class StaticTokenVerifier(TokenVerifier):

    async def verify_token(
        self,
        token: str,
    ) -> AccessToken | None:

        auth_info = KNOWN_TOKENS.get(token)

        if auth_info is None:
            logger.warning("Invalid token presented")
            return None

        logger.info(
            "Authenticated client: %s",
            auth_info.client_id,
        )

        return auth_info


# =====================================================
# 4. AUTHORIZATION POLICY
# =====================================================

class AuthorizationError(PermissionError):
    pass


def require_scope(scope: str) -> AccessToken:
    """
    Check the authenticated caller's permissions.

    Authentication has already happened in the
    MCP HTTP middleware.
    """

    auth = get_access_token()

    if auth is None:
        raise AuthorizationError(
            "Authentication required"
        )

    if scope not in auth.scopes:
        logger.warning(
            "Permission denied: client=%s scope=%s",
            auth.client_id,
            scope,
        )

        raise AuthorizationError(
            f"Missing required scope: {scope}"
        )

    return auth


# =====================================================
# 5. BUSINESS SERVICE
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
            raise ValueError(
                "Complex results are not supported"
            )

        return float(result)


def validate_numbers(a: float, b: float):
    if not (
        math.isfinite(a)
        and math.isfinite(b)
    ):
        raise ValueError(
            "Numbers must be finite"
        )


# =====================================================
# 6. INITIALIZE SECURED MCP SERVER
# =====================================================

mcp = MCPServer(
    "Secured Math MCP Server",
    version="1.0.0",
    instructions=(
        "Math tools, documentation and teaching "
        "prompts with scope-based authorization."
    ),
    token_verifier=StaticTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(DEMO_ISSUER),
        resource_server_url=AnyHttpUrl(
            RESOURCE_URL
        ),
        required_scopes=["math:read"],
        validate_token_resource=True,
    ),
)


# =====================================================
# 7. AUTHENTICATED IDENTITY TOOL
# =====================================================

@mcp.tool()
def whoami() -> dict:
    """Show the authenticated caller."""

    auth = require_scope("math:read")

    return {
        "client_id": auth.client_id,
        "scopes": auth.scopes,
    }


# =====================================================
# 8. PROTECTED MCP TOOLS
# =====================================================

def execute_math(operation, a, b):
    """
    Shared authorization and validation boundary.

    All arithmetic tools use this function.
    """
    auth = require_scope("math:execute")

    validate_numbers(a, b)

    result = operation(a, b)

    logger.info(
        "Math executed by %s: %s",
        auth.client_id,
        operation.__name__,
    )

    return result


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""

    return execute_math(
        MathService.add, a, b
    )


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""

    return execute_math(
        MathService.subtract, a, b
    )


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""

    return execute_math(
        MathService.multiply, a, b
    )


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b."""

    return execute_math(
        MathService.divide, a, b
    )


@mcp.tool()
def power(a: float, b: float) -> float:
    """Raise a to the power of b."""

    return execute_math(
        MathService.power, a, b
    )


# =====================================================
# 9. PROTECTED STATIC RESOURCE
# =====================================================

@mcp.resource(
    "math://guide",
    mime_type="text/markdown",
)
def math_guide() -> str:
    """Math server documentation."""

    require_scope("math:read")

    return """
# Math MCP Server

Available operations:

- add(a, b)
- subtract(a, b)
- multiply(a, b)
- divide(a, b)
- power(a, b)

Users with math:read can access documentation.

Users with math:execute can execute math tools.

Division by zero is not allowed.
"""


# =====================================================
# 10. PROTECTED RESOURCE TEMPLATE
# =====================================================

OPERATION_DOCS = {
    "add": "Combine two numbers.",
    "subtract": "Subtract b from a.",
    "multiply": "Multiply two numbers.",
    "divide": "Divide a by b.",
    "power": "Raise a to exponent b.",
}


@mcp.resource(
    "math://operations/{operation}",
    mime_type="text/plain",
)
def operation_documentation(
    operation: str,
) -> str:
    """Read math operation documentation."""

    require_scope("math:read")

    description = OPERATION_DOCS.get(operation)

    if description is None:
        raise ValueError(
            f"Unknown operation: {operation}"
        )

    return (
        f"Operation: {operation}\n"
        f"Description: {description}"
    )


# =====================================================
# 11. PROTECTED PROMPTS
# =====================================================

@mcp.prompt()
def explain_calculation(
    expression: str,
) -> str:
    """Explain a calculation step by step."""

    require_scope("math:read")

    return f"""
Explain this expression:

{expression}

Explain each mathematical operation.
Use MCP tools if actual calculation is needed.
Never invent tool results.
"""


@mcp.prompt()
def teach_operation(
    operation: str,
) -> str:
    """Teach a mathematical operation."""

    require_scope("math:read")

    return f"""
Teach the mathematical operation: {operation}

Include:
1. Definition
2. Simple example
3. Common mistakes
4. Two practice questions
"""


# =====================================================
# 12. APPLICATION ENTRY POINT
# =====================================================

if __name__ == "__main__":

    logger.info(
        "Starting secured MCP at %s",
        RESOURCE_URL,
    )

    mcp.run(
        transport="streamable-http",
        host=HOST,
        port=PORT,
        stateless_http=True,
        json_response=True,
        max_request_body_size=1024 * 1024,
    )
