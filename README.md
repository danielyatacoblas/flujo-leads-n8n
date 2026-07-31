# 01 · Flujo de leads con n8n — captación → CRM → newsletter → aviso al equipo

[![tests](https://img.shields.io/badge/tests-33%20passed-brightgreen)](tests/)
[![n8n](https://img.shields.io/badge/n8n-self--hosted-orange)](docker-compose.yml)
[![licencia](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

**Valida del aviso:** evaluar el stack Make + n8n · gestión de leads y
mensajería · email marketing · *"que un lead de Podium se sincronice
automáticamente con la lista de newsletter"*.

---

## 🎬 Qué hace (en una imagen)

```
Formulario web / Podium
        │  POST webhook
        ▼
   ┌─────────────────── n8n ───────────────────┐
   │ 1. Normalizar   nombre, email, tel +51    │
   │ 2. Validar      ¿contacto utilizable?     │──✗──► descartado (con motivo)
   │ 3. Deduplicar   ¿ya existe en el CRM?     │──↻──► duplicado (no re-suscribe)
   │ 4. Segmentar    talleres/voluntariado/    │
   │                 donación/general          │
   └──────────────────┬────────────────────────┘
                      ▼  (lead nuevo y válido)
   ┌──────────────────┴──────────────────┐
   ▼            ▼              ▼          ▼
 CRM        Newsletter    Email de    Aviso al
(Sheets)   (tag=segmento) bienvenida  equipo (Telegram)
                      │
                      ▼
        ⏰ 48 h sin contacto → recordatorio automático
```

---

## ⚡ Probarlo en 2 minutos (sin instalar n8n)

```bash
pip install pytest                     # única dependencia
python scripts/generar_data.py         # genera 44 leads ficticios
python scripts/simular_flujo.py        # corre el flujo completo en local
python -m pytest tests/ -v             # 33 tests
```

Salida real de `simular_flujo.py`:

```
Leads recibidos:   44
  ✓ nuevos:        40
  ↻ duplicados:    2   (no se re-registran ni re-suscriben)
  ✗ inválidos:     2   (sin contacto utilizable)

Por segmento (nuevos):
  talleres      19
  voluntariado  5
  donacion      7
  general       9

Seguimiento 48 h (simulando que el equipo ya atendió a 14):
  26 leads siguen 'nuevo' tras 48 h → recordatorio automático
```

También puedes abrir `formulario_demo/index.html` directo en el navegador:
funciona en **modo simulado** (misma lógica en JS) sin levantar nada.

---

## 🐳 Probarlo con n8n de verdad (gratis, local)

```bash
docker compose up -d                   # levanta n8n en http://localhost:5678
```

1. Entra a <http://localhost:5678> (usuario `admin`, clave `club-stem-demo`).
2. **Workflows → Import from File** → elige `workflows/workflow_leads_demo.json`.
3. Pulsa **Active** (arriba a la derecha).
4. Abre el nodo *Webhook* y copia la **Production URL**.
5. Abre `formulario_demo/index.html`, pega esa URL en el panel derecho y envía
   el formulario: verás la respuesta real de n8n con el segmento detectado.

> El workflow **demo no necesita ninguna credencial**: el CRM vive en la
> memoria del workflow (`workflowStaticData`). Es el que puede ejecutar
> cualquier persona que reciba el repo.

### Versión producción

`workflows/workflow_leads.json` es la versión real (12 nodos) con Google
Sheets como CRM, Mailchimp para newsletter, Telegram para avisos y un
*Schedule Trigger* cada 6 h para el seguimiento a 48 h. Requiere configurar:

| Nodo | Qué reemplazar | Dónde se obtiene |
| --- | --- | --- |
| CRM · Leer/Registrar | `REEMPLAZAR_ID_HOJA` | ID de la URL de la Google Sheet |
| Newsletter · Suscribir | `REEMPLAZAR_ID_LISTA` | Mailchimp → Audience → Settings |
| Equipo · Avisar | `REEMPLAZAR_CHAT_ID` | Telegram: hablarle a `@userinfobot` |

Estructura esperada de la hoja CRM (pestaña `Leads`):

```
nombre | email | telefono | mensaje | canal | fecha | segmento | estado
```

---

## 🧪 Cómo está probado (lo que lo hace confiable)

| Área | Qué se verifica |
| --- | --- |
| Normalización | Teléfono en 5 formatos distintos → siempre `+51#########` |
| Validación | Acepta con solo email **o** solo teléfono; rechaza sin nombre o sin contacto |
| Deduplicación | Detecta duplicado por email y por teléfono *escrito distinto* |
| Segmentación | 7 mensajes reales → segmento correcto; ignora tildes y mayúsculas |
| Acciones | Newsletter, bienvenida y notificación correctas por segmento |
| Seguimiento | Dispara a las 48 h, no antes, y **no** alcanza a los ya contactados |
| **Paridad JS ↔ Python** | El nodo Code de n8n y la lógica Python dan **resultados idénticos** sobre los 44 leads |

Ese último test es el más importante del repo: evita que el código del
workflow y el código probado se desincronicen en silencio.

```bash
python -m pytest tests/ -v
# 33 passed
```

---

## 📁 Estructura

```
01_flujo_leads_n8n/
├── src/flujo_leads.py            # lógica del flujo (1 función por nodo)
├── workflows/
│   ├── src/procesar_lead.js      # código del nodo Code, legible y revisable
│   ├── workflow_leads_demo.json  # importable, corre SIN credenciales
│   └── workflow_leads.json       # producción (Sheets + Mailchimp + Telegram)
├── scripts/
│   ├── generar_data.py           # data ficticia reproducible (seed fija)
│   ├── simular_flujo.py          # ejecuta el flujo end-to-end en local
│   └── build_workflow.py         # inyecta el JS en los workflows
├── formulario_demo/index.html    # formulario que dispara el webhook
├── tests/                        # 33 tests (incluye paridad JS↔Python)
├── data/leads_ficticios.csv      # 44 leads (con duplicados e inválidos)
├── docker-compose.yml            # n8n self-hosted
└── DECISION_N8N_VS_MAKE.md       # análisis y plan de consolidación
```

---

## 🔐 Decisiones de diseño

- **Ningún dato real**: la data ficticia se genera con semilla fija (`seed=42`),
  es reproducible y no contiene información de personas reales.
- **Credenciales fuera del código**: solo por el credential store de n8n o
  variables de entorno. El repo no contiene secretos.
- **Auditoría**: cada evento queda en `data/log_eventos.jsonl` (en producción,
  en una pestaña "Log" de la hoja).
- **Portable**: cambiar Google Sheets por Postgres/Supabase solo implica
  cambiar dos nodos; la lógica no se toca.
- **Sin dependencias pesadas**: Python estándar + pytest. Corre en cualquier
  máquina en segundos.

---

## 📌 Estado

✅ **Funcional y probado en local.** Workflows importables, 33 tests en verde,
data ficticia incluida. Listo para conectar credenciales reales del Club.
