"""Utilidades proporcionadas para adaptar y presentar las etiquetas.

Los ejercicios seleccionan los campos de cada contrato y las operaciones entre
conjuntos. Estas utilidades resuelven validación, normalización textual y formato.
"""

import math
import unicodedata


def normalize_labels(items, provider, label_field, confidence_field, scale):
    """Adaptar una colección sin modificarla ni calibrar los modelos entre sí.

Conservar la primera detección válida de cada key. Los registros incompletos,
vacíos o con confianza inválida se descartan; una colección inválida falla.
"""
    if not isinstance(items, list):
        raise ValueError("La colección de etiquetas debe ser una lista")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("La escala debe ser un número positivo y finito")
    labels = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get(label_field)
        confidence = item.get(confidence_field)
        if not isinstance(label, str) or not label.strip():
            continue
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            continue
        if not math.isfinite(confidence) or not 0 <= confidence <= scale:
            continue
        key = " ".join(unicodedata.normalize("NFKC", label).casefold().split())
        if key in seen:
            continue
        seen.add(key)
        labels.append({
            "provider": provider,
            "label": label,
            "key": key,
            "confidence": confidence / scale,
            "originalConfidence": confidence,
            "originalScale": f"0-{scale:g}",
        })
    return labels


def index_by_key(labels):
    """Construir un índice que conserva el primer registro de cada key."""
    index = {}
    for label in labels:
        index.setdefault(label["key"], label)
    return index


def build_comparison(vision_index, rekognition_index, common_keys, only_vision_keys, only_rekognition_keys):
    """Presentar las keys elegidas sin calcular su intersección ni diferencias."""
    return {
        "common": [
            {"key": key, "vision": vision_index[key], "rekognition": rekognition_index[key]}
            for key in sorted(common_keys)
        ],
        "onlyVision": [vision_index[key] for key in sorted(only_vision_keys)],
        "onlyRekognition": [rekognition_index[key] for key in sorted(only_rekognition_keys)],
    }
