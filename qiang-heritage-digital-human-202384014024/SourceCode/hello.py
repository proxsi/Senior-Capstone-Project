# Minimal Python entry-point smoke example.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Smallest possible HTTP server used to confirm the runtime can bind a port."""
from http.server import BaseHTTPRequestHandler, HTTPServer

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """Minimal request handler used only as a smoke test of the standard library server."""

    def do_GET(self):
        """Return a fixed HTML greeting for every GET request."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Hello, World!")

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    """Run the standalone demonstration HTTP server on port 8080."""
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

if __name__ == "__main__":
    run()