"""Bloques que se completan durante el laboratorio MPR.

Conservar los nombres y las firmas. La etapa upload funciona sin completar estos
ejercicios; cada etapa posterior utiliza los bloques indicados en el README.
"""

from normalization import build_comparison, index_by_key, normalize_labels


def analyze_vision(image_bytes, api_key, max_labels=10):
    # EJERCICIO 1: consultar Cloud Vision por HTTP para analizar la imagen.
    # Investigar su autenticación y contratos; devolver la respuesta JSON completa.
    raise NotImplementedError("Completar la consulta HTTP a Cloud Vision")


def detect_rekognition(client, image_bytes, max_labels=10):
    # EJERCICIO 2: consultar Rekognition mediante el cliente SDK proporcionado.
    # Analizar la imagen, aplicar max_labels y conservar la respuesta completa.
    raise NotImplementedError("Completar DetectLabels")


def normalize_vision(raw):
    # EJERCICIO 3a: identificar la colección de detecciones de Vision y llamar
    # normalize_labels con su proveedor, campos de etiqueta/confianza y escala.
    # No modificar raw ni reimplementar la normalización proporcionada.
    raise NotImplementedError("Completar el adaptador de Cloud Vision")


def normalize_rekognition(raw):
    # EJERCICIO 3b: identificar la colección de detecciones de Rekognition y
    # llamar normalize_labels con los campos y la escala de este contrato.
    raise NotImplementedError("Completar el adaptador de Rekognition")


def compare_labels(vision_labels, rekognition_labels):
    vision_index = index_by_key(vision_labels)
    rekognition_index = index_by_key(rekognition_labels)
    vision_keys = set(vision_index)
    rekognition_keys = set(rekognition_index)

    # EJERCICIO 4: reemplazar cada None por una operación entre los conjuntos
    # vision_keys y rekognition_keys. La presentación del resultado está resuelta.
    common_keys = None
    only_vision_keys = None
    only_rekognition_keys = None
    if any(keys is None for keys in (common_keys, only_vision_keys, only_rekognition_keys)):
        raise NotImplementedError("Completar la comparación de etiquetas")
    return build_comparison(
        vision_index, rekognition_index, common_keys, only_vision_keys, only_rekognition_keys)
