#!/usr/bin/env python3
"""Enviar una imagen a Lambda y mostrar la respuesta JSON."""

from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


# Copie aquí el valor FunctionUrl del stack.
LAMBDA_URL = ""


def main():
    if len(sys.argv) != 2:
        print(f'Uso: python3 {Path(sys.argv[0]).name} "ruta/a/imagen.jpg"', file=sys.stderr)
        return 1

    try:
        if not LAMBDA_URL.strip():
            raise ValueError("Configure LAMBDA_URL con la Function URL de Lambda.")
        image = Path(sys.argv[1]).read_bytes()
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            content_type = "image/png"
        elif image.startswith(b"\xff\xd8\xff"):
            content_type = "image/jpeg"
        else:
            raise ValueError("El archivo debe contener una imagen JPEG o PNG.")

        url = LAMBDA_URL.strip().rstrip("/")
        if not url.endswith("/analyze"):
            url += "/analyze"
        request = Request(
            url,
            data=image,
            headers={"Content-Type": content_type, "Accept": "application/json"},
            method="POST",
        )
        try:
            response = urlopen(request, timeout=100)
        except HTTPError as error:
            response = error
        with response:
            status = response.status
            payload = json.load(response)
    except (OSError, ValueError, HTTPException) as error:
        print(f"No se completó la solicitud: {error}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"HTTP {status}", file=sys.stderr)
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
