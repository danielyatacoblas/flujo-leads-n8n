"""Lógica del flujo de leads — espejo exacto de los nodos del workflow n8n.

Cada función corresponde a un nodo del workflow (`workflows/workflow_leads.json`),
para poder probar la lógica localmente con pytest sin depender de n8n ni de
credenciales externas:

    Webhook → normalizar → validar → deduplicar → segmentar → acciones
                                                    └→ seguimiento 48 h

La data "real" del Club viviría en Google Sheets; aquí se simula con listas
de dicts (mismas columnas que la hoja CRM).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

# ── Catálogo de segmentos (mismo orden de prioridad que el nodo IF de n8n) ──
SEGMENTOS = ("talleres", "voluntariado", "donacion", "general")

_KEYWORDS = {
    "talleres": ("taller", "clase", "curso", "robot", "program", "stem",
                 "inscri", "hij", "alumn"),
    "voluntariado": ("voluntari", "ayudar", "ensenar", "mentor", "apoyar"),
    "donacion": ("donar", "donacion", "aporte", "auspicio", "sponsor",
                 "empresa", "rse"),
}

SEG_HORAS_SEGUIMIENTO = 48   # sin contacto en 48 h → recordatorio


# ── Nodo 1: normalizar ──────────────────────────────────────────────────────

def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def normalizar_lead(crudo: dict) -> dict:
    """Limpia el payload del formulario: espacios, mayúsculas, teléfono a
    formato peruano E.164 (+51#########)."""
    nombre = " ".join(str(crudo.get("nombre", "")).split()).title()
    email = str(crudo.get("email", "")).strip().lower()
    telefono = re.sub(r"[^\d+]", "", str(crudo.get("telefono", "")))
    if telefono.startswith("+51"):
        pass
    elif telefono.startswith("51") and len(telefono) == 11:
        telefono = "+" + telefono
    elif len(telefono) == 9:
        telefono = "+51" + telefono
    mensaje = " ".join(str(crudo.get("mensaje", "")).split())
    return {
        "nombre": nombre,
        "email": email,
        "telefono": telefono,
        "mensaje": mensaje,
        "canal": str(crudo.get("canal", "web")).strip().lower() or "web",
        "fecha": str(crudo.get("fecha", "")) or datetime.now().isoformat(timespec="seconds"),
    }


# ── Nodo 2: validar ─────────────────────────────────────────────────────────

def validar_lead(lead: dict) -> tuple[bool, str]:
    """Un lead es válido con nombre y al menos un medio de contacto real."""
    if not lead.get("nombre"):
        return False, "sin nombre"
    email_ok = bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", lead.get("email", "")))
    tel_ok = bool(re.fullmatch(r"\+51\d{9}", lead.get("telefono", "")))
    if not (email_ok or tel_ok):
        return False, "sin email ni teléfono válidos"
    return True, "ok"


# ── Nodo 3: deduplicar contra el CRM ────────────────────────────────────────

def es_duplicado(lead: dict, crm: list[dict]) -> bool:
    """Duplicado si el email o el teléfono ya existen en la hoja CRM."""
    for fila in crm:
        if lead["email"] and lead["email"] == fila.get("email"):
            return True
        if lead["telefono"] and lead["telefono"] == fila.get("telefono"):
            return True
    return False


# ── Nodo 4: segmentar ───────────────────────────────────────────────────────

def segmentar(lead: dict) -> str:
    """Asigna el segmento por palabras clave del mensaje (sin tildes,
    minúsculas). Si nada matchea → 'general'."""
    texto = _sin_tildes(lead.get("mensaje", "").lower())
    for seg in ("donacion", "voluntariado", "talleres"):   # del más específico al más común
        if any(k in texto for k in _KEYWORDS[seg]):
            return seg
    return "general"


# ── Nodo 5: acciones (newsletter + bienvenida + notificación) ───────────────

_BIENVENIDA = {
    "talleres": ("¡Hola {nombre}! Gracias por tu interés en los talleres STEM "
                 "del Club. Aquí tienes el calendario del mes y el enlace de "
                 "inscripción."),
    "voluntariado": ("¡Hola {nombre}! Nos alegra que quieras ser voluntario/a. "
                     "Te contamos cómo funciona el programa y los próximos "
                     "onboarding."),
    "donacion": ("Hola {nombre}, gracias por querer apoyar al Club STEM. "
                 "Te compartimos las formas de aportar y el impacto de cada "
                 "una."),
    "general": ("¡Hola {nombre}! Gracias por escribirnos al Club STEM. "
                "Un miembro del equipo te contactará muy pronto."),
}


def construir_acciones(lead: dict, segmento: str) -> dict:
    """Qué hace el flujo con un lead nuevo válido (mismo orden que en n8n)."""
    return {
        "crm_fila": {**lead, "segmento": segmento, "estado": "nuevo"},
        "newsletter": {"email": lead["email"], "tag": segmento,
                       "accion": "suscribir" if lead["email"] else "omitir"},
        "email_bienvenida": _BIENVENIDA[segmento].format(nombre=lead["nombre"].split()[0]),
        "notificacion_equipo": (f"🔔 Nuevo lead [{segmento}] {lead['nombre']} "
                                f"({lead['canal']}) — {lead['email'] or lead['telefono']}"),
    }


# ── Nodo 6: seguimiento 48 h ────────────────────────────────────────────────

def necesita_seguimiento(fila_crm: dict, ahora: datetime) -> bool:
    """True si el lead sigue 'nuevo' y pasaron ≥48 h desde su registro."""
    if fila_crm.get("estado") != "nuevo":
        return False
    try:
        creado = datetime.fromisoformat(fila_crm["fecha"])
    except (KeyError, ValueError):
        return False
    return (ahora - creado) >= timedelta(hours=SEG_HORAS_SEGUIMIENTO)


# ── Pipeline completo (lo que hace el workflow de punta a punta) ────────────

def procesar_lead(crudo: dict, crm: list[dict]) -> dict:
    """Procesa un payload del formulario contra el CRM actual.

    Devuelve {"resultado": "nuevo"|"duplicado"|"invalido", ...} y, si es
    nuevo, agrega la fila al CRM (igual que haría el nodo de Google Sheets).
    """
    lead = normalizar_lead(crudo)
    ok, motivo = validar_lead(lead)
    if not ok:
        return {"resultado": "invalido", "motivo": motivo, "lead": lead}
    if es_duplicado(lead, crm):
        return {"resultado": "duplicado", "lead": lead}
    segmento = segmentar(lead)
    acciones = construir_acciones(lead, segmento)
    crm.append(acciones["crm_fila"])
    return {"resultado": "nuevo", "segmento": segmento, **acciones}
