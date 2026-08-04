#!/usr/bin/env python3
"""Genera data ficticia de leads (CSV) para probar el flujo sin datos reales.

    python scripts/generar_data.py            # data/leads_ficticios.csv (45 leads)

Incluye a propósito: duplicados (mismo email o teléfono), leads inválidos
(sin contacto), teléfonos en formatos mixtos y mensajes de los 4 segmentos.
"""
from __future__ import annotations

import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "leads_ficticios.csv"

random.seed(42)   # reproducible: mismos leads en cada corrida

NOMBRES = ["María Quispe", "jorge huamán", "Lucía Fernández", "CARLOS ROJAS",
           "Ana Paredes", "Pedro Castillo Vega", "Rosa Mamani", "diego torres",
           "Elena Vásquez", "Luis Chávez", "Carmen Flores", "José Gutiérrez",
           "Patricia Ramos", "Miguel Salas", "Sofía Herrera", "Raúl Ponce",
           # Apellidos con apóstrofo y nombres compuestos: rompen las
           # implementaciones ingenuas de "capitalizar cada palabra".
           "lucía d'angelo", "ANA-MARÍA TORRES", "josé o'brien"]

MENSAJES = {
    "talleres": [
        "Quiero inscribir a mi hija en el taller de robótica",
        "¿Cuándo empiezan las clases de programación para niños?",
        "Me interesa el curso de STEM del sábado",
        "Hola, busco talleres de ciencia para mi hijo de 10 años",
    ],
    "voluntariado": [
        "Me gustaría ser voluntario los fines de semana",
        "Soy estudiante y quiero apoyar enseñando",
        "¿Cómo puedo ayudar como mentor en el club?",
    ],
    "donacion": [
        "Represento a una empresa y queremos hacer un aporte",
        "Quisiera donar equipos para los talleres",
        "Nos interesa un auspicio como parte de nuestro programa de RSE",
    ],
    "general": [
        "Hola, quisiera más información",
        "¿Dónde están ubicados?",
        "Vi su publicación en Facebook y tengo una consulta",
    ],
}

CANALES = ["web", "facebook", "instagram", "podium", "referido"]


def _tel() -> str:
    n = "9" + "".join(str(random.randint(0, 9)) for _ in range(8))
    return random.choice([n, "+51" + n, "51" + n,
                          f"{n[:3]} {n[3:6]} {n[6:]}"])


def main():
    base = datetime(2026, 7, 1, 9, 0)
    filas = []
    for i in range(40):
        nombre = random.choice(NOMBRES)
        seg = random.choices(list(MENSAJES), weights=[5, 2, 1, 3])[0]
        email = (nombre.split()[0].lower().replace("í", "i").replace("é", "e")
                 .replace("á", "a").replace("ó", "o") + str(i) + "@example.com")
        filas.append({
            "nombre": nombre,
            "email": email,
            "telefono": _tel(),
            "mensaje": random.choice(MENSAJES[seg]),
            "canal": random.choice(CANALES),
            "fecha": (base + timedelta(hours=i * 3)).isoformat(timespec="seconds"),
        })

    # duplicados intencionales (mismo email / mismo teléfono, distinto formato)
    dup1 = dict(filas[3]); dup1["nombre"] = dup1["nombre"] + " "   # mismo email
    dup2 = dict(filas[7]); dup2["email"] = "otro_correo@example.com"  # mismo teléfono
    # inválidos intencionales
    inv1 = {"nombre": "Sin Contacto", "email": "no-es-email", "telefono": "123",
            "mensaje": "hola", "canal": "web", "fecha": base.isoformat()}
    inv2 = {"nombre": "", "email": "vacio@example.com", "telefono": "",
            "mensaje": "hola", "canal": "web", "fecha": base.isoformat()}
    filas += [dup1, dup2, inv1, inv2]
    random.shuffle(filas)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(filas[0].keys(, lineterminator="
")))
        wr.writeheader()
        wr.writerows(filas)
    print(f"✓ {OUT.relative_to(ROOT)} — {len(filas)} leads ficticios "
          f"(2 duplicados y 2 inválidos a propósito)")


if __name__ == "__main__":
    main()
