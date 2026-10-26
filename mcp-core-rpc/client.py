
import json
import uuid
from urllib.request import Request, urlopen


RPC_URL = "http://127.0.0.1:8000/rpc"


def rpc_call(method: str, params: dict):

    request_id = str(uuid.uuid4())

    ## construct the JSON-RPC request payload
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }

    ## serialize the payload to JSON and encode it to bytes
    body = json.dumps(payload).encode("utf-8")      


    ## send the HTTP POST request to the RPC server
    http_request = Request(
        url=RPC_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urlopen(http_request, timeout=5) as response:
        result = json.loads(response.read())

    ## verification
    if result.get("id") != request_id:
        raise ValueError("Mismatched request ID in response")

    ## error handling: check if the response contains an error
    if "error" in result:
        raise ValueError(f"RPC Error: {result['error']}")

    return result["result"]


if __name__ == "__main__":
    print("Addition:", rpc_call("add", {"a": 10, "b": 20}))
    print("Multiplication:", rpc_call("multiply", {"a": 5, "b": 6}))
