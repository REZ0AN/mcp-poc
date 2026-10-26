
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# simple RPC methods for execution
def add(a: int, b: int) -> int:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


# mapping of method names to functions
METHODS = {
    "add": add,
    "multiply": multiply,
}

# RPCHandler class to handle JSON-RPC requests
class RPCHandler(BaseHTTPRequestHandler):

    def do_POST(self):

        ## check if the request path is /rpc
        if self.path != "/rpc":
            self.send_error(404, "Not Found")
            return

        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            ## check if the request body is empty
            if content_length == 0:
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    },
                    "id": None
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            # check if the request body is too large
            if content_length > 1024:
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Request too large"
                    },
                    "id": None
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            ## check if the request headers are valid
            if self.headers.get("Content-Type") != "application/json":
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    },
                    "id": None
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            body = self.rfile.read(content_length)
            request = json.loads(body)

            # extract method, params, and id from the request
            method = request.get("method")
            params = request.get("params")
            request_id = request.get("id")

            ## check if the method is valid
            if method not in METHODS:
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": "Method not found"
                    },
                    "id": request_id
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            ## check if the id is valid
            if not isinstance(request_id, (str, int)):
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    },
                    "id": None
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            ## check if the method is a string
            if not isinstance(method, str):
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "Invalid Request"
                    },
                    "id": request_id
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return


            ## normalizing params into a list of arguments for the method call
            if isinstance(params, dict):
                args = [params.get("a"), params.get("b")]
            elif isinstance(params, list):
                args = params
            else:
                args = None

            ## check if the params are valid    
            if (
                args is None
                or len(args) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in args)
            ):
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params"
                    },
                    "id": request_id
                }
                payload = json.dumps(response).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            result = METHODS[method](*args)
            # call the method with the provided parameters
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }

        except Exception as exc:

            ## catch any unexpected errors and return an internal error response
            response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal error"
                },
                "id": request_id
            }
            payload = json.dumps(response).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        
        payload = json.dumps(response).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8000),
        RPCHandler
    )

    print("RPC server running on localhost:8000")
    server.serve_forever()
