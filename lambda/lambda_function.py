"""Carga y análisis sincrónico de una imagen mediante una Lambda Function URL.

La recepción HTTP y el almacenamiento están completos. Las consultas a los
proveedores y los adaptadores se completan en stages.py. No se crean clientes
AWS ni conexiones al importar este módulo.
"""

import base64
import binascii
import json
import logging
import os
import re
import socket
from urllib.error import HTTPError, URLError
import uuid

import stages


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_LABELS = 10
STAGES = {"upload", "vision", "rekognition", "compare"}


class InputError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class ProviderError(Exception):
    def __init__(self, code, message, raw=None):
        self.code, self.message, self.raw = code, message, raw


def _aws_client(service):
    # Lambda incluye Boto3. La importación diferida facilita pruebas sin AWS.
    import boto3
    from botocore.config import Config

    return boto3.client(service, config=Config(
        connect_timeout=3,
        read_timeout=15,
        retries={"total_max_attempts": 1},
    ))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "isBase64Encoded": False,
        "body": json.dumps(body, ensure_ascii=False, allow_nan=False),
    }


def _read_image(event):
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        raise InputError(400, "INVALID_REQUEST", "Los headers no son válidos.")
    headers = {str(key).lower(): value for key, value in headers.items()}
    content_type = headers.get("content-type", "")
    if not isinstance(content_type, str):
        content_type = ""
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png"}:
        raise InputError(415, "UNSUPPORTED_MEDIA_TYPE", "Enviar bytes JPEG o PNG con su Content-Type.")
    body = event.get("body")
    if not isinstance(body, str) or not body:
        raise InputError(400, "INVALID_BODY", "El body debe contener una imagen.")
    if event.get("isBase64Encoded") is not True:
        raise InputError(400, "INVALID_ENCODING", "La Function URL debe entregar la imagen binaria en base64.")
    if len(body) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise InputError(413, "IMAGE_TOO_LARGE", "La imagen debe tener como máximo 4 MiB.")
    try:
        image = base64.b64decode(body, validate=True)
    except (ValueError, binascii.Error):
        raise InputError(400, "INVALID_BASE64", "El body no contiene base64 válido.") from None
    if not image:
        raise InputError(400, "EMPTY_IMAGE", "La imagen está vacía.")
    if len(image) > MAX_IMAGE_BYTES:
        raise InputError(413, "IMAGE_TOO_LARGE", "La imagen debe tener como máximo 4 MiB.")
    signatures = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
    if not image.startswith(signatures[content_type]):
        raise InputError(400, "INVALID_IMAGE", "La firma del archivo no corresponde al Content-Type.")
    return image, content_type, "jpg" if content_type == "image/jpeg" else "png"


def _safe_code(value, fallback):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else fallback


def _redact_secret(value, secret):
    # Se conserva el contrato de la respuesta sin devolver accidentalmente la key
    # si el proveedor llegara a incluirla en el detalle de un error.
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]")
    if isinstance(value, list):
        return [_redact_secret(item, secret) for item in value]
    if isinstance(value, dict):
        return {key: _redact_secret(item, secret) for key, item in value.items()}
    return value


def _reject_json_constant(value):
    raise ValueError("La respuesta contiene una constante que no pertenece a JSON")


def _vision(image):
    secret = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not secret:
        raise ProviderError("GOOGLE_API_KEY_MISSING", "Configurar GOOGLE_API_KEY en las variables de entorno de Lambda.")
    try:
        raw = stages.analyze_vision(image, secret, MAX_LABELS)
    except HTTPError as exception:
        status = exception.code
        raw = None
        try:
            raw = json.load(exception, parse_constant=_reject_json_constant)
        except (ValueError, UnicodeError, OSError):
            pass
        finally:
            exception.close()
        if raw is not None:
            raw = _redact_secret(raw, secret)
        raise ProviderError(f"VISION_HTTP_{status}", "Cloud Vision rechazó la solicitud HTTP.", raw) from None
    except (URLError, TimeoutError, socket.timeout):
        raise ProviderError("VISION_CONNECTION_ERROR", "No fue posible completar la conexión con Cloud Vision.") from None
    except (ValueError, UnicodeError):
        raise ProviderError("VISION_INVALID_RESPONSE", "Cloud Vision no devolvió JSON válido.") from None
    raw = _redact_secret(raw, secret)
    responses = raw.get("responses") if isinstance(raw, dict) else None
    if not isinstance(responses, list) or len(responses) != 1 or not isinstance(responses[0], dict):
        raise ProviderError("VISION_INVALID_RESPONSE", "Se esperaba una respuesta para una imagen.", raw)
    provider_error = responses[0].get("error")
    if provider_error:
        code = provider_error.get("code") if isinstance(provider_error, dict) else None
        code = f"VISION_ERROR_{code}" if isinstance(code, int) and not isinstance(code, bool) else "VISION_API_ERROR"
        raise ProviderError(code, "Cloud Vision informó un error para la imagen.", raw)
    return raw


def _provider_call(operation):
    try:
        raw = operation()
        return {"status": "ok", "raw": raw}
    except NotImplementedError:
        return {"status": "pending", "error": {
            "code": "EXERCISE_PENDING", "message": "Completar el ejercicio de esta etapa en stages.py."}}
    except ProviderError as exception:
        result = {"status": "error", "error": {
            "code": exception.code, "message": exception.message}}
        if exception.raw is not None:
            result["raw"] = exception.raw
        return result
    except Exception as exception:
        # No devolver mensajes/tracebacks de SDK: pueden contener datos de entrada.
        provider_response = getattr(exception, "response", {})
        code = provider_response.get("Error", {}).get("Code") if isinstance(provider_response, dict) else None
        return {"status": "error", "error": {
            "code": _safe_code(code, "PROVIDER_ERROR"),
            "message": "El proveedor no pudo completar la operación; revisar configuración y permisos."}}


def _normalize_results(providers):
    adapters = {"vision": stages.normalize_vision, "rekognition": stages.normalize_rekognition}
    for name, result in providers.items():
        if result["status"] != "ok":
            continue
        try:
            result["labels"] = adapters[name](result["raw"])
        except NotImplementedError:
            result.update(status="pending", error={
                "code": "EXERCISE_PENDING", "message": "Completar el adaptador en stages.py."})
        except Exception:
            result.update(status="error", error={
                "code": "INVALID_PROVIDER_RESULT", "message": "No fue posible adaptar la respuesta del proveedor."})


def _put_object(bucket, key, body, content_type):
    try:
        _aws_client("s3").put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    except Exception as exception:
        sdk_response = getattr(exception, "response", {})
        sdk_error = sdk_response.get("Error") if isinstance(sdk_response, dict) else None
        code = sdk_error.get("Code") if isinstance(sdk_error, dict) else None
        raise InputError(
            502, "S3_" + _safe_code(code, "ERROR"),
            "No se pudo guardar el archivo en S3. Verificar DATA_BUCKET y el permiso s3:PutObject del rol de Lambda.",
        ) from None


def lambda_handler(event, context):
    request_id = uuid.uuid4().hex
    stage = os.environ.get("LAB_STAGE", "upload")
    result, providers = {}, {}

    def finish(status):
        provider_log = {}
        for name, item in providers.items():
            provider_log[name] = {"status": item["status"]}
            provider_error = item.get("error")
            if isinstance(provider_error, dict):
                result.setdefault("errors", {})[name] = provider_error
                provider_log[name]["errorCode"] = _safe_code(provider_error.get("code"), "PROVIDER_ERROR")
        LOGGER.info(json.dumps({
            "requestId": request_id,
            "awsRequestId": getattr(context, "aws_request_id", None),
            "stage": stage, "httpStatus": status,
            "providers": provider_log,
        }))
        return response(status, result)

    try:
        if stage not in STAGES:
            raise InputError(500, "CONFIGURATION_ERROR", "LAB_STAGE debe ser upload, vision, rekognition o compare.")
        http = (event.get("requestContext") or {}).get("http") or {}
        method, path = http.get("method"), event.get("rawPath")
        if method == "GET" and path == "/status":
            result.update(status="operational", stage=stage)
            return finish(200)
        if path != "/analyze":
            raise InputError(404, "ROUTE_NOT_FOUND", "Utilizar POST /analyze o GET /status.")
        if method != "POST":
            raise InputError(405, "METHOD_NOT_ALLOWED", "La imagen se envía mediante POST.")
        image, content_type, extension = _read_image(event)
        bucket = os.environ.get("DATA_BUCKET")
        if not bucket:
            raise InputError(500, "CONFIGURATION_ERROR", "Configurar DATA_BUCKET.")
        key = f"uploads/{request_id}.{extension}"
        _put_object(bucket, key, image, content_type)
        result["imageKey"] = key
        if stage == "upload":
            return finish(201)
        providers["vision"] = _provider_call(lambda: _vision(image))
        if "raw" in providers["vision"]:
            result["vision"] = providers["vision"]["raw"]
            _put_object(bucket, f"uploads/{request_id}.vision.json",
                json.dumps(providers["vision"]["raw"], ensure_ascii=False, allow_nan=False).encode("utf-8"),
                "application/json")
        if stage in {"rekognition", "compare"}:
            providers["rekognition"] = _provider_call(lambda: stages.detect_rekognition(
                _aws_client("rekognition"), image, MAX_LABELS))
            if "raw" in providers["rekognition"]:
                result["rekognition"] = providers["rekognition"]["raw"]
                _put_object(bucket, f"uploads/{request_id}.rekognition.json",
                    json.dumps(providers["rekognition"]["raw"], ensure_ascii=False, allow_nan=False).encode("utf-8"),
                    "application/json")
        if stage == "compare":
            _normalize_results(providers)
            if all(item["status"] == "ok" for item in providers.values()):
                result["comparison"] = stages.compare_labels(
                    providers["vision"]["labels"], providers["rekognition"]["labels"])
        states = [item["status"] for item in providers.values()]
        if "pending" in states:
            return finish(501)
        if all(state == "ok" for state in states):
            return finish(200)
        return finish(207 if "ok" in states else 502)
    except InputError as exception:
        result["error"] = {"code": exception.code, "message": exception.message}
        return finish(exception.status)
    except NotImplementedError:
        result["error"] = {"code": "EXERCISE_PENDING", "message": "Completar el ejercicio de esta etapa en stages.py."}
        return finish(501)
    except Exception:
        result["error"] = {"code": "SERVICE_ERROR", "message": "No fue posible completar la operación; revisar recursos y permisos."}
        return finish(500)
