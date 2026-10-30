
import json
import uuid

from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# =====================================================
# 1. CONFIGURATION
# =====================================================

RPC_URL = "http://127.0.0.1:8000/rpc"
DEFAULT_TIMEOUT = 5


# =====================================================
# 2. CLIENT EXCEPTIONS
# =====================================================

class RPCClientError(Exception):
    """Base exception for RPC client failures."""
    pass


class RPCTransportError(RPCClientError):
    """HTTP or network communication failure."""
    pass


class RPCProtocolError(RPCClientError):
    """Invalid JSON-RPC response from the server."""
    pass


class RPCRemoteError(RPCClientError):
    """JSON-RPC error returned by the remote server."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

        super().__init__(
            f"RPC error {code}: {message}"
        )


# =====================================================
# 3. JSON-RPC CLIENT
# =====================================================

class RPCClient:

    def __init__(
        self,
        url: str,
        timeout: int = DEFAULT_TIMEOUT
    ):
        self.url = url
        self.timeout = timeout

    # -------------------------------------------------
    # Build JSON-RPC request
    # -------------------------------------------------

    def _build_request(
        self,
        method: str,
        params: dict | list | None,
        request_id: str
    ) -> dict:

        if not isinstance(method, str) or not method:
            raise ValueError("Invalid method")

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id
        }

        if params is not None:
            if not isinstance(params, (dict, list)):
                raise ValueError(
                    "Params must be a dict or list"
                )

            request["params"] = params

        return request

    # -------------------------------------------------
    # Send HTTP request
    # -------------------------------------------------

    def _send(self, payload: dict) -> dict:

        body = json.dumps(
            payload,
            allow_nan=False
        ).encode("utf-8")

        http_request = Request(
            url=self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )

        try:
            with urlopen(
                http_request,
                timeout=self.timeout
            ) as response:

                raw_body = response.read()

        except HTTPError as exc:
            raise RPCTransportError(
                f"HTTP error: {exc.code}"
            ) from exc

        except URLError as exc:
            raise RPCTransportError(
                f"Connection failed: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise RPCTransportError(
                "RPC request timed out"
            ) from exc

        try:
            result = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RPCProtocolError(
                "Server returned invalid JSON"
            ) from exc

        if not isinstance(result, dict):
            raise RPCProtocolError(
                "Expected a JSON-RPC response object"
            )

        return result

    # -------------------------------------------------
    # Validate server response
    # -------------------------------------------------

    def _validate_response(
        self,
        response: dict,
        request_id: str
    ) -> Any:

        if response.get("jsonrpc") != "2.0":
            raise RPCProtocolError(
                "Unsupported JSON-RPC version"
            )

        if (
            "id" not in response
            or response["id"] != request_id
        ):
            raise RPCProtocolError(
                "Response ID does not match request ID"
            )

        has_result = "result" in response
        has_error = "error" in response

        # Exactly one must exist
        if has_result == has_error:
            raise RPCProtocolError(
                "Response must contain either "
                "result or error"
            )

        if has_error:
            error = response["error"]

            if not isinstance(error, dict):
                raise RPCProtocolError(
                    "Invalid error object"
                )

            code = error.get("code")
            message = error.get("message")

            if (
                not isinstance(code, int)
                or isinstance(code, bool)
                or not isinstance(message, str)
            ):
                raise RPCProtocolError(
                    "Invalid error code or message"
                )

            raise RPCRemoteError(code, message)

        return response["result"]

    # -------------------------------------------------
    # Public API: Execute remote procedure
    # -------------------------------------------------

    def call(
        self,
        method: str,
        params: dict | list | None = None
    ) -> Any:

        request_id = str(uuid.uuid4())

        request = self._build_request(
            method,
            params,
            request_id
        )

        response = self._send(request)

        return self._validate_response(
            response,
            request_id
        )


# =====================================================
# 4. APPLICATION ENTRY POINT
# =====================================================

def main():

    client = RPCClient(RPC_URL)

    try:
        addition = client.call(
            "add",
            {"a": 10, "b": 20}
        )

        print("Addition:", addition)

        multiplication = client.call(
            "multiply",
            [5, 6]
        )

        print("Multiplication:", multiplication)

        # Test a remote error
        client.call(
            "subtract",
            {"a": 10, "b": 5}
        )

    except RPCRemoteError as exc:
        print(
            f"Remote error: "
            f"{exc.code} - {exc.message}"
        )

    except RPCTransportError as exc:
        print("Transport error:", exc)

    except RPCProtocolError as exc:
        print("Protocol error:", exc)


if __name__ == "__main__":
    main()
