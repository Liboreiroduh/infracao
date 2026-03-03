#!/usr/bin/env python3
import argparse
import json
import os
import re
import unicodedata
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from autuacao_extractor import build_xlsx_bytes, extract_records_from_bytes, parse_codes


BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "web" / "index.html"
MAX_UPLOAD_SIZE = 25 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    default_host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    return parser.parse_args()


class AppHandler(BaseHTTPRequestHandler):
    server_version = "AutuacaoExcel/1.0"

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self.serve_health(send_body=False)
            return
        if path in {"/", "/index.html"}:
            self.serve_index(send_body=False)
            return
        self.send_error(404, "Página não encontrada.")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self.serve_health()
            return
        if path in {"/", "/index.html"}:
            self.serve_index()
            return
        self.send_error(404, "Página não encontrada.")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/process":
            self.handle_process()
            return
        self.send_error(404, "Página não encontrada.")

    def serve_index(self, send_body: bool = True) -> None:
        content = INDEX_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if send_body:
            self.wfile.write(content)

    def serve_health(self, send_body: bool = True) -> None:
        payload = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def handle_process(self) -> None:
        try:
            form, files = self.parse_form_data()
            codes = parse_codes(form.get("codes", ""))
            upload = files.get("pdf")
            if not upload:
                raise ValueError("Envie um arquivo PDF para processar.")

            filename, pdf_bytes, _content_type = upload
            if not pdf_bytes.startswith(b"%PDF-"):
                raise ValueError("O arquivo enviado não parece ser um PDF válido.")

            records = extract_records_from_bytes(pdf_bytes, codes)
            workbook = build_xlsx_bytes(records)
            output_name = make_output_name(filename)

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", f'attachment; filename="{output_name}"')
            self.send_header("Content-Length", str(len(workbook)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Result-Count", str(len(records)))
            self.send_header("X-Result-Codes", ",".join(codes))
            self.end_headers()
            self.wfile.write(workbook)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception:
            self.send_json({"error": "Falha ao processar o PDF."}, status=500)

    def parse_form_data(self) -> tuple[dict[str, str], dict[str, tuple[str, bytes, str]]]:
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", "0"))

        if not content_type.startswith("multipart/form-data"):
            raise ValueError("O formulário precisa ser enviado como multipart/form-data.")
        if content_length <= 0:
            raise ValueError("Nenhum conteúdo foi enviado.")
        if content_length > MAX_UPLOAD_SIZE:
            raise ValueError("O arquivo excede o limite de 25 MB.")

        body = self.rfile.read(content_length)
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )

        form: dict[str, str] = {}
        files: dict[str, tuple[str, bytes, str]] = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename is None:
                charset = part.get_content_charset() or "utf-8"
                form[name] = payload.decode(charset, "replace").strip()
                continue
            files[name] = (filename, payload, part.get_content_type())
        return form, files

    def send_json(self, payload: dict[str, str], status: int) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def make_output_name(filename: str) -> str:
    stem = Path(filename).stem
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_stem = "".join(char for char in normalized if not unicodedata.combining(char))
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_stem).strip("_") or "autuacoes"
    return f"{safe}_filtrado.xlsx"


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f"Servidor disponível em http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
