"""Tests del flujo de leads — se ejecutan con: pytest -v

Cubren cada nodo del workflow n8n: normalización, validación, deduplicación,
segmentación, acciones y seguimiento a 48 h.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.flujo_leads import (construir_acciones, es_duplicado,  # noqa: E402
                             necesita_seguimiento, normalizar_lead,
                             procesar_lead, segmentar, validar_lead)


# ── normalización ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("987654321", "+51987654321"),
    ("+51987654321", "+51987654321"),
    ("51987654321", "+51987654321"),
    ("987 654 321", "+51987654321"),
    ("987-654-321", "+51987654321"),
])
def test_normaliza_telefono_a_e164(entrada, esperado):
    lead = normalizar_lead({"nombre": "Ana", "telefono": entrada})
    assert lead["telefono"] == esperado


def test_normaliza_nombre_y_email():
    lead = normalizar_lead({"nombre": "  maRÍA   quispe ",
                            "email": "  MARIA@Example.COM "})
    assert lead["nombre"] == "María Quispe"
    assert lead["email"] == "maria@example.com"


def test_canal_por_defecto_es_web():
    assert normalizar_lead({"nombre": "Ana"})["canal"] == "web"


@pytest.mark.parametrize("entrada,esperado", [
    ("lucía d'angelo", "Lucía D'Angelo"),
    ("ANA-MARÍA TORRES", "Ana-María Torres"),
    ("josé o'brien", "José O'Brien"),
    ("maría del carmen", "María Del Carmen"),
])
def test_capitaliza_apellidos_con_apostrofo_y_guion(entrada, esperado):
    """Apellidos reales del Perú: partir solo por espacios daría 'D'angelo'.

    Este caso hacía divergir la implementación Python de la de JavaScript
    (ver tests/test_paridad_js.py).
    """
    assert normalizar_lead({"nombre": entrada})["nombre"] == esperado


# ── validación ──────────────────────────────────────────────────────────────

def test_valido_con_email_solamente():
    lead = normalizar_lead({"nombre": "Ana", "email": "ana@mail.com"})
    assert validar_lead(lead)[0] is True


def test_valido_con_telefono_solamente():
    lead = normalizar_lead({"nombre": "Ana", "telefono": "987654321"})
    assert validar_lead(lead)[0] is True


def test_invalido_sin_nombre():
    lead = normalizar_lead({"nombre": "", "email": "ana@mail.com"})
    ok, motivo = validar_lead(lead)
    assert ok is False and "nombre" in motivo


def test_invalido_sin_contacto_utilizable():
    lead = normalizar_lead({"nombre": "Ana", "email": "no-es-email",
                            "telefono": "123"})
    ok, motivo = validar_lead(lead)
    assert ok is False and "email" in motivo


# ── deduplicación ───────────────────────────────────────────────────────────

def test_detecta_duplicado_por_email():
    crm = [{"email": "ana@mail.com", "telefono": "+51999999999"}]
    lead = normalizar_lead({"nombre": "Ana", "email": "ANA@mail.com"})
    assert es_duplicado(lead, crm) is True


def test_detecta_duplicado_por_telefono_en_otro_formato():
    crm = [{"email": "ana@mail.com", "telefono": "+51987654321"}]
    lead = normalizar_lead({"nombre": "Ana", "email": "nueva@mail.com",
                            "telefono": "987 654 321"})
    assert es_duplicado(lead, crm) is True


def test_lead_nuevo_no_es_duplicado():
    crm = [{"email": "ana@mail.com", "telefono": "+51987654321"}]
    lead = normalizar_lead({"nombre": "Beto", "email": "beto@mail.com",
                            "telefono": "912345678"})
    assert es_duplicado(lead, crm) is False


# ── segmentación ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mensaje,esperado", [
    ("Quiero inscribir a mi hija en el taller de robótica", "talleres"),
    ("¿Cuándo empiezan las clases de programación?", "talleres"),
    ("Me gustaría ser voluntario los fines de semana", "voluntariado"),
    ("Quiero ayudar como mentor", "voluntariado"),
    ("Represento una empresa y queremos hacer un aporte", "donacion"),
    ("Quisiera donar equipos", "donacion"),
    ("Hola, quisiera más información", "general"),
])
def test_segmentacion_por_palabras_clave(mensaje, esperado):
    assert segmentar({"mensaje": mensaje}) == esperado


def test_segmentacion_ignora_tildes_y_mayusculas():
    assert segmentar({"mensaje": "QUIERO SER VOLUNTARIO"}) == "voluntariado"
    assert segmentar({"mensaje": "quiero una donacion"}) == "donacion"


# ── acciones ────────────────────────────────────────────────────────────────

def test_acciones_incluyen_newsletter_bienvenida_y_notificacion():
    lead = normalizar_lead({"nombre": "Ana Paredes", "email": "ana@mail.com",
                            "mensaje": "quiero el taller de robótica"})
    acc = construir_acciones(lead, "talleres")
    assert acc["newsletter"]["tag"] == "talleres"
    assert acc["newsletter"]["accion"] == "suscribir"
    assert "Ana" in acc["email_bienvenida"]
    assert "talleres" in acc["notificacion_equipo"]
    assert acc["crm_fila"]["estado"] == "nuevo"


def test_sin_email_no_se_suscribe_al_newsletter():
    lead = normalizar_lead({"nombre": "Ana", "telefono": "987654321"})
    acc = construir_acciones(lead, "general")
    assert acc["newsletter"]["accion"] == "omitir"


@pytest.mark.parametrize("segmento", ["talleres", "voluntariado", "donacion",
                                      "general"])
def test_el_email_de_bienvenida_no_deja_variables_sin_reemplazar(segmento):
    """El correo se envía tal cual a una familia: no puede llevar `{algo}`."""
    lead = normalizar_lead({"nombre": "Ana Paredes", "email": "ana@mail.com"})
    texto = construir_acciones(lead, segmento)["email_bienvenida"]
    assert "{" not in texto and "}" not in texto, (
        f"el correo de '{segmento}' saldría con una variable sin reemplazar: {texto}")
    assert texto.strip().endswith((".", "!", "?")), "debe cerrar bien la frase"


# ── seguimiento 48 h ────────────────────────────────────────────────────────

def test_seguimiento_dispara_tras_48h_sin_contacto():
    creado = datetime(2026, 7, 1, 9, 0)
    fila = {"estado": "nuevo", "fecha": creado.isoformat()}
    assert necesita_seguimiento(fila, creado + timedelta(hours=49)) is True


def test_seguimiento_no_dispara_antes_de_48h():
    creado = datetime(2026, 7, 1, 9, 0)
    fila = {"estado": "nuevo", "fecha": creado.isoformat()}
    assert necesita_seguimiento(fila, creado + timedelta(hours=47)) is False


def test_seguimiento_no_alcanza_a_leads_ya_contactados():
    creado = datetime(2026, 7, 1, 9, 0)
    fila = {"estado": "contactado", "fecha": creado.isoformat()}
    assert necesita_seguimiento(fila, creado + timedelta(days=10)) is False


# ── pipeline completo ───────────────────────────────────────────────────────

def test_pipeline_registra_lead_nuevo_en_crm():
    crm = []
    r = procesar_lead({"nombre": "Ana", "email": "ana@mail.com",
                       "mensaje": "quiero el taller"}, crm)
    assert r["resultado"] == "nuevo"
    assert r["segmento"] == "talleres"
    assert len(crm) == 1


def test_pipeline_rechaza_duplicado_sin_tocar_crm():
    crm = []
    payload = {"nombre": "Ana", "email": "ana@mail.com", "mensaje": "hola"}
    procesar_lead(payload, crm)
    r = procesar_lead(payload, crm)
    assert r["resultado"] == "duplicado"
    assert len(crm) == 1, "un duplicado no debe agregar fila al CRM"


def test_pipeline_rechaza_invalido():
    crm = []
    r = procesar_lead({"nombre": "X", "email": "malo", "telefono": "1"}, crm)
    assert r["resultado"] == "invalido"
    assert crm == []


def test_data_ficticia_procesa_completa():
    """Corre el pipeline sobre el CSV ficticio (si ya fue generado)."""
    import csv
    csv_path = ROOT / "data" / "leads_ficticios.csv"
    if not csv_path.exists():
        pytest.skip("corre antes: python scripts/generar_data.py")
    crm, res = [], []
    for fila in csv.DictReader(csv_path.open(encoding="utf-8")):
        res.append(procesar_lead(fila, crm)["resultado"])
    assert res.count("duplicado") >= 2, "la data trae 2 duplicados sembrados"
    assert res.count("invalido") >= 2, "la data trae 2 inválidos sembrados"
    assert len(crm) == res.count("nuevo")
