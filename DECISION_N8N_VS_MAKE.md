# Decisión técnica: n8n vs Make — cuándo usar cada uno

> Documento de trabajo para la responsabilidad *"Evaluar nuestro stack actual
> (Make + n8n) y recomendar qué herramienta usar según el caso de uso,
> identificando oportunidades de consolidación o migración"*.
>
> Los precios son referenciales (planes públicos vigentes a julio 2026) y
> deben confirmarse con las cuentas reales del Club antes de decidir.

---

## 1. Resumen ejecutivo (para quien tiene 60 segundos)

| Pregunta | Respuesta corta |
| --- | --- |
| ¿Cuál es más barato a escala? | **n8n self-hosted** (0 S/ de licencia, solo el servidor). Make cobra por operación y cada paso cuenta. |
| ¿Cuál es más rápido de armar? | **Make**, para integraciones de apps populares con pocos pasos. |
| ¿Cuál conviene para el Club? | **Modelo híbrido con n8n como estándar**: todo lo nuevo y todo lo que tenga volumen o lógica propia va a n8n; Make se conserva solo donde ya funciona y su conector es superior. |
| ¿Qué migrar primero? | Los escenarios de **alto volumen de operaciones** (sincronización de leads, publicación programada), que son los que consumen el plan de Make. |

---

## 2. Comparación por criterio

| Criterio | n8n | Make |
| --- | --- | --- |
| **Modelo de costo** | Gratis self-hosted (Fair-code). Cloud desde ~US$ 20/mes por *ejecuciones* (un flujo de 20 pasos = 1 ejecución) | Por **operación**: cada módulo ejecutado cuenta. Plan Free ~1.000 ops/mes; Core ~US$ 9/mes por 10.000 ops |
| **Costo real a volumen** | Un flujo de 15 nodos × 1.000 leads = **1.000 ejecuciones** | El mismo flujo = **15.000 operaciones** → agota planes rápido |
| **Lógica personalizada** | Nodo **Code** con JavaScript/Python completo, librerías, sin límite práctico | Funciones y módulo *Tools*; código real solo con Custom Apps (más limitado) |
| **Conectores listos** | ~400+, muy buenos en dev-tools, HTTP, BD | ~1.500+, mejor cobertura de apps de marketing/ofimática |
| **Curva de aprendizaje** | Media (piensa en "datos que fluyen entre nodos") | Baja (muy visual, ideal para perfiles no técnicos) |
| **Versionado / Git** | Workflows son **JSON exportable** → viven en el repo, se revisan en PR | Exportación de escenarios (blueprint JSON) posible, pero menos integrado al flujo de desarrollo |
| **Auto-hospedaje** | Sí (Docker) — control total del dato | No (SaaS únicamente) |
| **Privacidad de datos** | Los datos de familias/beneficiarios pueden **no salir** de la infraestructura propia | Todo pasa por servidores de Make |
| **Manejo de errores** | Error Workflow global, reintentos por nodo, ramas de error | Manejo de errores por ruta, reintentos configurables |
| **Debug** | Ver datos de entrada/salida por nodo, re-ejecutar desde un nodo | Historial de ejecuciones con detalle por módulo |

---

## 3. Regla de decisión (la que aplicaría en el día a día)

```
¿El flujo maneja datos personales sensibles (familias, menores, beneficiarios)?
   SÍ → n8n self-hosted (el dato no sale de nuestra infraestructura)
   NO ↓
¿Va a correr más de ~500 veces al mes o tiene más de 8 pasos?
   SÍ → n8n (en Make cada paso multiplica el costo)
   NO ↓
¿Necesita lógica propia real (parsers, cálculos, transformaciones)?
   SÍ → n8n (nodo Code)
   NO ↓
¿Existe conector nativo en Make y no en n8n, y lo va a mantener alguien no técnico?
   SÍ → Make
   NO → n8n (estándar por defecto)
```

---

## 4. Aplicación a los casos del Club STEM

| Caso de uso | Recomendación | Por qué |
| --- | --- | --- |
| Sincronización de leads (Podium → CRM → newsletter) | **n8n** | Alto volumen, datos personales, lógica de dedupe y segmentación propia |
| Publicación programada en redes | **n8n** | Muchos pasos por post (generar, aprobar, publicar en 3 redes, leer métricas) → en Make serían ~10 ops por post |
| Email marketing / newsletters | **n8n** con API de Mailchimp/Brevo | Segmentación dinámica; el conector no es el cuello de botella |
| Alertas simples (formulario → Slack/email) | **Make** (si ya existe) | 2-3 operaciones, cero lógica: migrarlo no aporta valor |
| Extracción de KPIs desde varias fuentes | **n8n** + Apps Script | Transformaciones y agregaciones que requieren código |
| Integración con app sin conector en n8n | **Make** o n8n vía HTTP Request | Evaluar caso a caso: HTTP Request cubre casi todo si hay API REST |

---

## 5. Plan de consolidación propuesto (3 fases)

**Fase 1 — Inventario (semana 1-2).**
Listar todos los escenarios de Make y flujos de n8n con: qué hace, cuántas
operaciones/ejecuciones consume, criticidad y responsable. Sin inventario no
hay decisión informada, solo intuición.

**Fase 2 — Migrar los "caros" (semana 3-6).**
Ordenar por operaciones consumidas y migrar el top 20 % a n8n (suele ser el
80 % del consumo). Cada migración: reconstruir en n8n → correr **en paralelo**
con el escenario de Make unos días → comparar salidas → recién ahí apagar el de
Make. Nunca migrar en caliente sin ventana de comparación.

**Fase 3 — Estandarizar (continuo).**
- Todo flujo nuevo se construye en n8n salvo excepción justificada.
- Cada flujo se exporta a JSON y vive en el repo (revisable, versionado).
- Cada flujo tiene su ficha de documentación (ver proyecto `04`).
- Naming estándar: `[área] Acción — detalle` (ej. `[Leads] Alta — web a CRM`).

---

## 6. Riesgos y cómo mitigarlos

| Riesgo | Mitigación |
| --- | --- |
| n8n self-hosted se cae y nadie lo nota | Healthcheck + alerta a Telegram; backup diario de la BD de n8n |
| Dependencia de una sola persona (bus factor) | Documentación viva por flujo + workflows en Git, no solo en el servidor |
| Migración rompe un proceso activo | Correr en paralelo antes de apagar; checklist de verificación por flujo |
| Costos ocultos del hosting | n8n corre en un VPS de ~US$ 5-6/mes; sigue siendo menor que escalar Make |

---

## 7. Conclusión

Para el perfil del Club STEM —**volumen creciente, presupuesto ajustado, datos
sensibles de familias y necesidad de lógica propia**— la recomendación es
**estandarizar en n8n self-hosted y conservar Make solo como excepción
justificada**, ejecutando la migración por fases y priorizando por consumo.

Lo importante no es la herramienta, sino que cada flujo esté **documentado,
versionado y monitoreado**: eso es lo que hace que el sistema sobreviva a
quien lo construyó.
