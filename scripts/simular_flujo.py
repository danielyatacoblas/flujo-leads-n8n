#!/usr/bin/env python3
"""Simula el workflow completo de n8n en local, con la data ficticia.

    python scripts/generar_data.py       # primero genera los leads
    python scripts/simular_flujo.py      # procesa todo y muestra el resumen

Salidas (mismo contenido que dejaría el flujo real en Google Sheets):
    data/crm_resultado.csv     ← hoja CRM final
    data/log_eventos.jsonl     ← 1 línea por evento (auditoría)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.flujo_leads import necesita_seguimiento, procesar_lead  # noqa: E402

ENTRADA = ROOT / "data" / "leads_ficticios.csv"
CRM_OUT = ROOT / "data" / "crm_resultado.csv"
LOG_OUT = ROOT / "data" / "log_eventos.jsonl"


def main():
    if not ENTRADA.exists():
        raise SystemExit("Primero corre: python scripts/generar_data.py")

    crudos = list(csv.DictReader(ENTRADA.open(encoding="utf-8")))
    crm: list[dict] = []
    eventos = []
    stats = Counter()

    for crudo in crudos:
        r = procesar_lead(crudo, crm)
        stats[r["resultado"]] += 1
        ev = {"resultado": r["resultado"],
              "email": r["lead"]["email"] if "lead" in r else r["crm_fila"]["email"]}
        if r["resultado"] == "nuevo":
            ev["segmento"] = r["segmento"]
            ev["notificacion"] = r["notificacion_equipo"]
            stats[f"seg_{r['segmento']}"] += 1
        eventos.append(ev)

    # El equipo ya atendió a algunos leads (simulado): 1 de cada 3 pasa a
    # 'contactado' — así se ve que el seguimiento SOLO alcanza a los olvidados.
    for i, fila in enumerate(crm):
        if i % 3 == 0:
            fila["estado"] = "contactado"

    # simulación del seguimiento: "hoy" = 3 días después del último lead
    ahora = max(datetime.fromisoformat(f["fecha"]) for f in crm) + timedelta(days=3)
    pendientes = [f for f in crm if necesita_seguimiento(f, ahora)]
    contactados = sum(1 for f in crm if f["estado"] == "contactado")

    CRM_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CRM_OUT.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(crm[0].keys()))
        wr.writeheader()
        wr.writerows(crm)
    with LOG_OUT.open("w", encoding="utf-8") as f:
        for ev in eventos:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    print("=== Simulación del flujo de leads (local, data ficticia) ===\n")
    print(f"Leads recibidos:   {len(crudos)}")
    print(f"  ✓ nuevos:        {stats['nuevo']}")
    print(f"  = duplicados:    {stats['duplicado']}  (no se re-registran ni re-suscriben)")
    print(f"  ✗ inválidos:     {stats['invalido']}  (sin contacto utilizable)")
    print("\nPor segmento (nuevos):")
    for seg in ("talleres", "voluntariado", "donacion", "general"):
        print(f"  {seg:<13} {stats[f'seg_{seg}']}")
    print(f"\nSeguimiento 48 h (simulando que el equipo ya atendió a {contactados}):")
    print(f"  {len(pendientes)} leads siguen 'nuevo' tras 48 h → recordatorio automático")
    for f in pendientes[:3]:
        print(f"    · {f['nombre']} ({f['segmento']}) — registrado {f['fecha'][:10]}")
    if len(pendientes) > 3:
        print(f"    · … y {len(pendientes)-3} más")
    print(f"\n✓ CRM final:  {CRM_OUT.relative_to(ROOT)} ({len(crm)} filas)")
    print(f"✓ Auditoría:  {LOG_OUT.relative_to(ROOT)} ({len(eventos)} eventos)")


if __name__ == "__main__":
    main()
