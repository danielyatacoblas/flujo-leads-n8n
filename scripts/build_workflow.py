#!/usr/bin/env python3
"""Construye los workflows de n8n inyectando el código de workflows/src/*.js.

    python scripts/build_workflow.py

Genera:
  workflows/workflow_leads_demo.json  → importable y ejecutable SIN credenciales
  workflows/workflow_leads.json       → versión producción (Sheets + Mailchimp + Telegram)

Se mantiene el JS en archivos aparte (no como string escapado) para que sea
revisable en el repo y editable con resaltado de sintaxis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "workflows" / "src"
OUT = ROOT / "workflows"


def _cond(left: str, right: str, cid: str) -> dict:
    return {
        "options": {"caseSensitive": True, "leftValue": "",
                    "typeValidation": "strict", "version": 2},
        "conditions": [{
            "id": cid,
            "leftValue": left,
            "rightValue": right,
            "operator": {"type": "string", "operation": "equals"},
        }],
        "combinator": "and",
    }


def _node(nid, name, ntype, tv, pos, params, extra=None):
    n = {"parameters": params, "id": nid, "name": name, "type": ntype,
         "typeVersion": tv, "position": pos}
    if extra:
        n.update(extra)
    return n


def build_demo(js: str) -> dict:
    """Webhook → Procesar (Code) → Switch por segmento → Responder.

    Funciona en n8n recién instalado: no usa ninguna credencial.
    """
    nodes = [
        _node("wh-01", "Webhook · Nuevo lead", "n8n-nodes-base.webhook", 2,
              [-220, 300],
              {"httpMethod": "POST", "path": "lead-demo",
               "responseMode": "responseNode", "options": {}},
              {"webhookId": "club-stem-lead-demo"}),
        _node("code-01", "Procesar lead", "n8n-nodes-base.code", 2,
              [20, 300], {"jsCode": js}),
        _node("sw-01", "Enrutar por segmento", "n8n-nodes-base.switch", 3,
              [260, 300],
              {"rules": {"values": [
                  {"conditions": _cond("={{ $json.segmento }}", "talleres", "c1"),
                   "renameOutput": True, "outputKey": "talleres"},
                  {"conditions": _cond("={{ $json.segmento }}", "voluntariado", "c2"),
                   "renameOutput": True, "outputKey": "voluntariado"},
                  {"conditions": _cond("={{ $json.segmento }}", "donacion", "c3"),
                   "renameOutput": True, "outputKey": "donacion"},
              ]},
               "options": {"fallbackOutput": "extra",
                           "renameFallbackOutput": "otros"}}),
        _node("set-t", "Acción · Talleres", "n8n-nodes-base.set", 3.4,
              [520, 60],
              {"assignments": {"assignments": [
                  {"id": "a1", "name": "accion", "value": "Enviar calendario + link de inscripción",
                   "type": "string"}]}, "options": {}}),
        _node("set-v", "Acción · Voluntariado", "n8n-nodes-base.set", 3.4,
              [520, 220],
              {"assignments": {"assignments": [
                  {"id": "a2", "name": "accion", "value": "Enviar guía de onboarding de voluntarios",
                   "type": "string"}]}, "options": {}}),
        _node("set-d", "Acción · Donación", "n8n-nodes-base.set", 3.4,
              [520, 380],
              {"assignments": {"assignments": [
                  {"id": "a3", "name": "accion", "value": "Derivar a coordinación de alianzas",
                   "type": "string"}]}, "options": {}}),
        _node("set-g", "Acción · General / otros", "n8n-nodes-base.set", 3.4,
              [520, 540],
              {"assignments": {"assignments": [
                  {"id": "a4", "name": "accion", "value": "Respuesta genérica + asignar a bandeja",
                   "type": "string"}]}, "options": {}}),
        _node("resp-01", "Responder al formulario", "n8n-nodes-base.respondToWebhook", 1,
              [780, 300], {"respondWith": "allIncomingItems", "options": {}}),
    ]
    connections = {
        "Webhook · Nuevo lead": {"main": [[{"node": "Procesar lead", "type": "main", "index": 0}]]},
        "Procesar lead": {"main": [[{"node": "Enrutar por segmento", "type": "main", "index": 0}]]},
        "Enrutar por segmento": {"main": [
            [{"node": "Acción · Talleres", "type": "main", "index": 0}],
            [{"node": "Acción · Voluntariado", "type": "main", "index": 0}],
            [{"node": "Acción · Donación", "type": "main", "index": 0}],
            [{"node": "Acción · General / otros", "type": "main", "index": 0}],
        ]},
        "Acción · Talleres": {"main": [[{"node": "Responder al formulario", "type": "main", "index": 0}]]},
        "Acción · Voluntariado": {"main": [[{"node": "Responder al formulario", "type": "main", "index": 0}]]},
        "Acción · Donación": {"main": [[{"node": "Responder al formulario", "type": "main", "index": 0}]]},
        "Acción · General / otros": {"main": [[{"node": "Responder al formulario", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Club STEM · Leads (DEMO sin credenciales)",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"instanceId": "club-stem-demo"},
        "tags": [{"name": "club-stem"}, {"name": "demo"}],
    }


def build_prod(js: str) -> dict:
    """Versión producción: Sheets (CRM) + Mailchimp + Telegram + seguimiento 48 h.

    Requiere configurar credenciales en n8n (ver README).
    """
    js_prod = js.replace(
        "const store = $getWorkflowStaticData('global');\nif (!Array.isArray(store.crm)) store.crm = [];",
        "// En producción el CRM llega del nodo Google Sheets anterior\n"
        "const store = { crm: $('CRM · Leer hoja').all().map((i) => i.json) };")

    nodes = [
        _node("wh-1", "Webhook · Nuevo lead", "n8n-nodes-base.webhook", 2,
              [-260, 300],
              {"httpMethod": "POST", "path": "lead", "responseMode": "lastNode",
               "options": {}},
              {"webhookId": "club-stem-lead"}),
        _node("gs-read", "CRM · Leer hoja", "n8n-nodes-base.googleSheets", 4.5,
              [-40, 300],
              {"documentId": {"__rl": True, "value": "REEMPLAZAR_ID_HOJA", "mode": "id"},
               "sheetName": {"__rl": True, "value": "Leads", "mode": "name"},
               "options": {}},
              {"alwaysOutputData": True,
               "notes": "Hoja CRM: columnas nombre,email,telefono,mensaje,canal,fecha,segmento,estado"}),
        _node("code-1", "Procesar lead", "n8n-nodes-base.code", 2,
              [180, 300], {"jsCode": js_prod}),
        _node("if-1", "¿Es lead nuevo?", "n8n-nodes-base.if", 2,
              [400, 300],
              {"conditions": _cond("={{ $json.resultado }}", "nuevo", "cif"),
               "options": {}}),
        _node("gs-append", "CRM · Registrar lead", "n8n-nodes-base.googleSheets", 4.5,
              [640, 180],
              {"operation": "append",
               "documentId": {"__rl": True, "value": "REEMPLAZAR_ID_HOJA", "mode": "id"},
               "sheetName": {"__rl": True, "value": "Leads", "mode": "name"},
               "columns": {"mappingMode": "autoMapInputData", "value": {}},
               "options": {}}),
        _node("mc-1", "Newsletter · Suscribir", "n8n-nodes-base.mailchimp", 1,
              [880, 100],
              {"list": "REEMPLAZAR_ID_LISTA",
               "email": "={{ $json.crm_fila.email }}",
               "status": "subscribed",
               "options": {"tagsUi": {"tagValues": [
                   {"name": "={{ $json.segmento }}"}]}}},
              {"notes": "Alternativa gratuita: HTTP Request a la API de Brevo"}),
        _node("tg-1", "Equipo · Avisar por Telegram", "n8n-nodes-base.telegram", 1.2,
              [880, 260],
              {"chatId": "REEMPLAZAR_CHAT_ID",
               "text": "={{ $json.notificacion_equipo }}",
               "additionalFields": {}}),
        _node("noop-dup", "Duplicado · Solo log", "n8n-nodes-base.noOp", 1,
              [640, 420], {}),
        # ── seguimiento 48 h ──
        _node("cron-1", "Cada 6 horas", "n8n-nodes-base.scheduleTrigger", 1.2,
              [-260, 640],
              {"rule": {"interval": [{"field": "hours", "hoursInterval": 6}]}}),
        _node("gs-read2", "CRM · Leer para seguimiento", "n8n-nodes-base.googleSheets", 4.5,
              [-40, 640],
              {"documentId": {"__rl": True, "value": "REEMPLAZAR_ID_HOJA", "mode": "id"},
               "sheetName": {"__rl": True, "value": "Leads", "mode": "name"},
               "options": {}}),
        _node("code-2", "Filtrar > 48 h sin contacto", "n8n-nodes-base.code", 2,
              [180, 640],
              {"jsCode": (
                  "// Devuelve los leads que siguen 'nuevo' tras 48 h\n"
                  "const LIMITE_MS = 48 * 60 * 60 * 1000;\n"
                  "const ahora = Date.now();\n"
                  "return $input.all().filter((i) => {\n"
                  "  const f = i.json;\n"
                  "  if (f.estado !== 'nuevo') return false;\n"
                  "  const creado = Date.parse(f.fecha);\n"
                  "  return !isNaN(creado) && (ahora - creado) >= LIMITE_MS;\n"
                  "});\n")}),
        _node("tg-2", "Equipo · Recordatorio de seguimiento", "n8n-nodes-base.telegram", 1.2,
              [400, 640],
              {"chatId": "REEMPLAZAR_CHAT_ID",
               "text": "=⏰ Lead sin contactar hace +48 h: {{ $json.nombre }} "
                       "({{ $json.segmento }}) — {{ $json.email }}",
               "additionalFields": {}}),
    ]
    connections = {
        "Webhook · Nuevo lead": {"main": [[{"node": "CRM · Leer hoja", "type": "main", "index": 0}]]},
        "CRM · Leer hoja": {"main": [[{"node": "Procesar lead", "type": "main", "index": 0}]]},
        "Procesar lead": {"main": [[{"node": "¿Es lead nuevo?", "type": "main", "index": 0}]]},
        "¿Es lead nuevo?": {"main": [
            [{"node": "CRM · Registrar lead", "type": "main", "index": 0}],
            [{"node": "Duplicado · Solo log", "type": "main", "index": 0}],
        ]},
        "CRM · Registrar lead": {"main": [[
            {"node": "Newsletter · Suscribir", "type": "main", "index": 0},
            {"node": "Equipo · Avisar por Telegram", "type": "main", "index": 0},
        ]]},
        "Cada 6 horas": {"main": [[{"node": "CRM · Leer para seguimiento", "type": "main", "index": 0}]]},
        "CRM · Leer para seguimiento": {"main": [[{"node": "Filtrar > 48 h sin contacto", "type": "main", "index": 0}]]},
        "Filtrar > 48 h sin contacto": {"main": [[{"node": "Equipo · Recordatorio de seguimiento", "type": "main", "index": 0}]]},
    }
    return {
        "name": "Club STEM · Leads (producción)",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "meta": {"instanceId": "club-stem-prod"},
        "tags": [{"name": "club-stem"}, {"name": "leads"}],
    }


def main():
    js = (SRC / "procesar_lead.js").read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for nombre, wf in (("workflow_leads_demo.json", build_demo(js)),
                       ("workflow_leads.json", build_prod(js))):
        p = OUT / nombre
        p.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✓ {p.relative_to(ROOT)} — {len(wf['nodes'])} nodos")
    print("\nImporta el DEMO en n8n (Workflows → Import from File) y actívalo:")
    print("  funciona sin ninguna credencial.")


if __name__ == "__main__":
    main()
