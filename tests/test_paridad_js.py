"""Test de paridad: el nodo Code de n8n (JS) debe dar el MISMO resultado que
la implementación Python sobre la misma data ficticia.

Evita el riesgo clásico de tener dos implementaciones que se desincronizan:
si alguien toca procesar_lead.js sin tocar flujo_leads.py (o al revés),
este test falla.

Requiere Node.js instalado. Si no está, el test se salta (no rompe la suite).
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.flujo_leads import procesar_lead  # noqa: E402

CSV = ROOT / "data" / "leads_ficticios.csv"
RUNNER = ROOT / "tests" / "correr_nodo_js.mjs"


def _resultado_python() -> list[dict]:
    crm: list[dict] = []
    salida = []
    for fila in csv.DictReader(CSV.open(encoding="utf-8")):
        r = procesar_lead(fila, crm)
        base = r.get("crm_fila") or r["lead"]
        salida.append({
            "resultado": r["resultado"],
            "segmento": r.get("segmento"),
            "email": base["email"],
            "telefono": base["telefono"],
            "nombre": base["nombre"],
        })
    return salida


def _resultado_js() -> list[dict]:
    proc = subprocess.run(
        ["node", str(RUNNER), str(CSV)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    if proc.returncode != 0:
        pytest.fail(f"el nodo JS falló:\n{proc.stderr}")
    return json.loads(proc.stdout)


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="Node.js no está instalado")
def test_js_y_python_dan_el_mismo_resultado():
    if not CSV.exists():
        pytest.skip("corre antes: python scripts/generar_data.py")

    py = _resultado_python()
    js = _resultado_js()

    assert len(py) == len(js), "distinta cantidad de leads procesados"

    diferencias = [(i, p, j) for i, (p, j) in enumerate(zip(py, js)) if p != j]
    assert not diferencias, (
        "el nodo n8n (JS) y la lógica Python divergen en "
        f"{len(diferencias)} leads. Primera: idx={diferencias[0][0]}\n"
        f"  python={diferencias[0][1]}\n  js    ={diferencias[0][2]}")


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="Node.js no está instalado")
def test_js_detecta_los_mismos_duplicados_e_invalidos():
    if not CSV.exists():
        pytest.skip("corre antes: python scripts/generar_data.py")
    js = _resultado_js()
    conteo = {k: sum(1 for r in js if r["resultado"] == k)
              for k in ("nuevo", "duplicado", "invalido")}
    assert conteo["duplicado"] >= 2
    assert conteo["invalido"] >= 2
    assert conteo["nuevo"] > 0
