
import json
import uuid

from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# =====================================================
# 1. CONFIGURATION
# =====================================================

RPC_URL = "http://127.0.0.1:8000/rpc"
TIMEOUT = 5


# =====================================================
# 2. CLIENT ERRORS
# =====================================================

class RPCClientError(Exception):
    pass


class RPCTransportError(RPCClientError):
    pass


class RPCProtocolError(RPCClientError):
    pass


class RPCRemoteError(RPCClientError):

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class ToolExecutionError(RPCClientError):
    pass


# =====================================================
# 3. RAW JSON-RPC CLIENT
# =====================================================

class RPCClient:

    def __init__(self, url: str):
        self.url = url

    def rpc_call(
        self,
        method: str,
        params: dict | None = None
    ) -> Any:

        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id
        }

        if params is not None:
            payload["params"] = params

        body = json.dumps(payload).encode("utf-8")

        request = Request(
            url=self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )

        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                raw_response = response.read()

        except HTTPError as exc:
            raise RPCTransportError(
                f"HTTP status: {exc.code}"
            ) from exc

        except (URLError, TimeoutError) as exc:
            raise RPCTransportError(
                f"Transport failure: {exc}"
            ) from exc

        try:
            response_data = json.loads(raw_response)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RPCProtocolError(
                "Invalid JSON response"
            ) from exc

        if not isinstance(response_data, dict):
            raise RPCProtocolError(
                "Response must be a JSON object"
            )

        if response_data.get("jsonrpc") != "2.0":
            raise RPCProtocolError(
                "Invalid JSON-RPC version"
            )

        if (
            "id" not in response_data
            or response_data["id"] != request_id
        ):
            raise RPCProtocolError(
                "Request ID mismatch"
            )

        has_result = "result" in response_data
        has_error = "error" in response_data

        if has_result == has_error:
            raise RPCProtocolError(
                "Expected exactly one result or error"
            )

        if has_error:
            error = response_data["error"]

            if (
                not isinstance(error, dict)
                or type(error.get("code")) is not int
                or not isinstance(
                    error.get("message"), str
                )
            ):
                raise RPCProtocolError(
                    "Invalid JSON-RPC error object"
                )

            raise RPCRemoteError(
                error["code"],
                error["message"]
            )

        return response_data["result"]

    # -------------------------------------------------
    # Tool discovery
    # -------------------------------------------------

    def list_tools(self) -> list[dict]:

        result = self.rpc_call("tools/list")

        if (
            not isinstance(result, dict)
            or not isinstance(result.get("tools"), list)
        ):
            raise RPCProtocolError(
                "Invalid tools/list result"
            )

        return result["tools"]

    # -------------------------------------------------
    # Tool invocation
    # -------------------------------------------------

    def call_tool(
        self,
        name: str,
        arguments: dict
    ) -> dict:

        result = self.rpc_call(
            "tools/call",
            {
                "name": name,
                "arguments": arguments
            }
        )

        if (
            not isinstance(result, dict)
            or not isinstance(result.get("content"), list)
            or not isinstance(
                result.get("isError", False), bool
            )
        ):
            raise RPCProtocolError(
                "Invalid tools/call result"
            )

        if result.get("isError", False):

            messages = [
                item.get("text", "")
                for item in result["content"]
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                )
            ]

            raise ToolExecutionError(
                "\n".join(messages)
                or "Tool execution failed"
            )

        return result


# =====================================================
# 4. APPLICATION ENTRY POINT
# =====================================================

def main():

    client = RPCClient(RPC_URL)

    # 1. Discover tools dynamically
    print("=== AVAILABLE TOOLS ===")

    tools = client.list_tools()

    for tool in tools:
        print(f"\nName: {tool['name']}")
        print(f"Description: {tool['description']}")
        print(
            "Input schema:",
            json.dumps(tool["inputSchema"])
        )

    # 2. Execute a discovered tool
    print("\n=== EXECUTE ADD ===")

    result = client.call_tool(
        "add",
        {"a": 10, "b": 20}
    )

    print(json.dumps(result, indent=2))

    # 3. Execute a second tool
    print("\n=== EXECUTE MULTIPLY ===")

    result = client.call_tool(
        "multiply",
        {"a": 5, "b": 6}
    )

    print(json.dumps(result, indent=2))

    # 4. Execute the subtract tool
    print("\n=== EXECUTE SUBTRACT ===")
    result = client.call_tool(
        "subtract",
        {"a": 10, "b": 5}
    )   
    print(json.dumps(result, indent=2))

    # 5. Test a business logic error
    print("\n=== DIVIDE BY ZERO ===")

    try:
        client.call_tool(
            "divide",
            {"a": 10, "b": 0}
        )
    except ToolExecutionError as exc:
        print("Tool error:", exc)

    # 6. Test an unknown tool
    print("\n=== UNKNOWN TOOL ===")

    try:
        client.call_tool(
            "concatenate",
            {"a": 10, "b": 5}
        )
    except RPCRemoteError as exc:
        print("RPC error:", exc)


if __name__ == "__main__":
    main()
