from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from neuzelaar.core.session import BrowserSession


def test_session_submits_post_form_to_fixture_server() -> None:
    server = HTTPServer(("127.0.0.1", 0), _FormServer)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = BrowserSession()
        session.open_url(f"http://127.0.0.1:{server.server_port}/form")

        result = session.submit_form(1, {"comment": "hello"})

        assert result.resource.final_url == f"http://127.0.0.1:{server.server_port}/submit"
        assert "Received name=guest&comment=hello" in result.rendered_text
    finally:
        server.shutdown()
        thread.join(timeout=2)


class _FormServer(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/form":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"""<!doctype html>
<html>
<head><title>Server Form</title></head>
<body>
<form action="/submit" method="post">
  <input name="name" value="guest">
  <textarea name="comment">default</textarea>
  <button type="submit">Send</button>
</form>
</body>
</html>"""
        )

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            f"""<!doctype html>
<html>
<head><title>Server Form Result</title></head>
<body><h1>Received {body}</h1></body>
</html>""".encode("utf-8")
        )

    def log_message(self, format, *args) -> None:
        return
