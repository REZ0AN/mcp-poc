
import inspect
import json
import logging
import math

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


# =====================================================
# 1. CONFIGURATION
# =====================================================

HOST = "127.0.0.1"
PORT = 8000
MAX_BODY_SIZE = 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rpc-server")


# =====================================================
# 2. SERVICE LAYER
# =====================================================

class MathService:

    @staticmethod
    def add(a: float, b: float) -> float:
        return a + b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    @staticmethod
    def subtract(a: float, b: float) -> float:
        return a - b


# =====================================================
# 3. JSON-RPC ERROR TYPES
# =====================================================

class RPCError(Exception):

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ParseError(RPCError):
    def __init__(self):
        super().__init__(-32700, "Parse error")


class InvalidRequest(RPCError):
    def __init__(self):
        super().__init__(-32600, "Invalid Request")


class MethodNotFound(RPCError):
    def __init__(self):
        super().__init__(-32601, "Method not found")


class InvalidParams(RPCError):
    def __init__(self, message="Invalid params"):
        super().__init__(-32602, message)


# =====================================================
# 4. GLOBAL ERROR HANDLING
# =====================================================

class GlobalErrorHandler:

    @staticmethod
    def handle(error: Exception, request_id=None) -> dict:

        if isinstance(error, RPCError):
            code = error.code
            message = error.message
        else:
            logger.error(
                "Unexpected RPC error",
                exc_info=(
                    type(error),
                    error,
                    error.__traceback__
                )
            )
            code = -32603
            message = "Internal error"

        return {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            },
            "id": request_id
        }


# =====================================================
# 5. TOOL REGISTRY
# =====================================================

@dataclass
class Tool:
    name: str
    description: str
    function: Callable
    input_schema: dict

    def metadata(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        function: Callable,
        input_schema: dict
    ):
        if name in self._tools:
            raise ValueError(f"Duplicate tool: {name}")

        self._tools[name] = Tool(
            name=name,
            description=description,
            function=function,
            input_schema=input_schema
        )

    def list_tools(self) -> list[dict]:
        return [
            self._tools[name].metadata()
            for name in sorted(self._tools)
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:

        tool = self._tools.get(name)

        if tool is None:
            raise InvalidParams(f"Unknown tool: {name}")

        if not isinstance(arguments, dict):
            raise InvalidParams(
                "Tool arguments must be an object"
            )

        # Minimal schema validation for our numeric tools.
        # This is not a general JSON Schema validator.
        schema = tool.input_schema
        properties = schema["properties"]
        required = schema.get("required", [])

        for field in required:
            if field not in arguments:
                return self._tool_error(
                    f"Missing required argument: {field}"
                )

        for field, value in arguments.items():
            if field not in properties:
                return self._tool_error(
                    f"Unknown argument: {field}"
                )

            expected = properties[field].get("type")

            if expected == "number":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    return self._tool_error(
                        f"Argument '{field}' must be a finite number"
                    )

        try:
            # Check Python function argument compatibility.
            signature = inspect.signature(tool.function)
            bound = signature.bind(**arguments)

        except TypeError:
            return self._tool_error("Invalid tool arguments")

        try:
            result = tool.function(
                *bound.args,
                **bound.kwargs
            )

            # Ensure result can be represented in JSON.
            json.dumps(result, allow_nan=False)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result)
                    }
                ],
                "isError": False
            }

        except ValueError as exc:
            # Expected business failure
            return self._tool_error(str(exc))

        except Exception:
            logger.exception("Tool execution failed")
            return self._tool_error(
                "Tool execution failed"
            )

    @staticmethod
    def _tool_error(message: str) -> dict:
        return {
            "content": [
                {
                    "type": "text",
                    "text": message
                }
            ],
            "isError": True
        }


# =====================================================
# 6. REGISTER TOOLS
# =====================================================

registry = ToolRegistry()


def math_schema():
    return {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["a", "b"],
        "additionalProperties": False
    }


registry.register(
    name="add",
    description="Add two numbers",
    function=MathService.add,
    input_schema=math_schema()
)

registry.register(
    name="multiply",
    description="Multiply two numbers",
    function=MathService.multiply,
    input_schema=math_schema()
)

registry.register(
    name="divide",
    description="Divide a number by another",
    function=MathService.divide,
    input_schema=math_schema()
)

registry.register(
    name="subtract",
    description="Subtract one number from another",
    function=MathService.subtract,
    input_schema=math_schema()
)

# =====================================================
# 7. RPC CONTROLLER
# =====================================================

class RPCController:

    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry

    def execute(self, request: Any) -> dict | None:

        request_id = None
        valid_notification = False

        try:
            if not isinstance(request, dict):
                raise InvalidRequest()

            # Preserve a valid ID for error correlation.
            if "id" in request:
                candidate = request["id"]

                if not (
                    candidate is None
                    or isinstance(candidate, str)
                    or (
                        type(candidate) in (int, float)
                        and math.isfinite(candidate)
                    )
                ):
                    raise InvalidRequest()

                request_id = candidate

            if request.get("jsonrpc") != "2.0":
                raise InvalidRequest()

            method = request.get("method")

            if (
                not isinstance(method, str)
                or not method
                or method.startswith("rpc.")
            ):
                raise InvalidRequest()

            params = request.get("params", {})

            if not isinstance(params, dict):
                raise InvalidParams()

            valid_notification = "id" not in request

            if method == "tools/list":
                if params:
                    raise InvalidParams(
                        "tools/list accepts no arguments in this demo"
                    )

                result = {
                    "tools": self.registry.list_tools()
                }

            elif method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments", {})

                if not isinstance(name, str):
                    raise InvalidParams("Tool name is required")

                if not isinstance(arguments, dict):
                    raise InvalidParams(
                        "arguments must be an object"
                    )

                result = self.registry.call_tool(
                    name,
                    arguments
                )

            else:
                raise MethodNotFound()

            if valid_notification:
                return None

            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }

        except Exception as exc:

            if valid_notification:
                logger.warning(
                    "Notification failed: %s", exc
                )
                return None

            return GlobalErrorHandler.handle(
                exc,
                request_id
            )


# =====================================================
# 8. HTTP TRANSPORT
# =====================================================

class RPCHandler(BaseHTTPRequestHandler):

    controller = RPCController(registry)

    def do_POST(self):

        if self.path != "/rpc":
            self.send_error(404)
            return

        try:
            if self.headers.get_content_type() != "application/json":
                self.send_error(415)
                return

            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            if content_length <= 0:
                raise ParseError()

            if content_length > MAX_BODY_SIZE:
                self.send_error(413)
                return

            body = self.rfile.read(content_length)

            try:
                request = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                raise ParseError()

            response = self.controller.execute(request)

            if response is None:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            self.send_json(response)

        except Exception as exc:
            response = GlobalErrorHandler.handle(exc)
            self.send_json(response)

    def send_json(self, response: dict):

        payload = json.dumps(
            response,
            allow_nan=False
        ).encode("utf-8")

        self.send_response(200)
        self.send_header(
            "Content-Type", "application/json"
        )
        self.send_header(
            "Content-Length", str(len(payload))
        )
        self.end_headers()
        self.wfile.write(payload)


# =====================================================
# 9. APPLICATION ENTRY POINT
# =====================================================

if __name__ == "__main__":

    server = ThreadingHTTPServer(
        (HOST, PORT),
        RPCHandler
    )

    print(f"RPC server: http://{HOST}:{PORT}/rpc")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        server.server_close()
