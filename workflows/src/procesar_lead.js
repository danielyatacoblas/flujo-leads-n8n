// Nodo Code de n8n — "Procesar lead"
// Espejo en JavaScript de src/flujo_leads.py (misma lógica, misma salida).
// La paridad entre ambos está cubierta por tests/test_paridad_js.py.
// Se inyecta en el workflow con: python scripts/build_workflow.py
//
// El CRM demo vive en workflowStaticData para que el flujo funcione SIN
// credenciales de Google Sheets (en producción lo reemplaza el nodo Sheets).

const KEYWORDS = {
  donacion: ['donar', 'donacion', 'aporte', 'auspicio', 'sponsor', 'empresa', 'rse'],
  voluntariado: ['voluntari', 'ayudar', 'ensenar', 'mentor', 'apoyar'],
  talleres: ['taller', 'clase', 'curso', 'robot', 'program', 'stem', 'inscri', 'hij', 'alumn'],
};

const BIENVENIDA = {
  talleres: '¡Hola {nombre}! Gracias por tu interés en los talleres STEM del Club. Aquí tienes el calendario del mes y el enlace de inscripción.',
  voluntariado: '¡Hola {nombre}! Nos alegra que quieras ser voluntario/a. Te contamos cómo funciona el programa y los próximos onboarding.',
  donacion: 'Hola {nombre}, gracias por querer apoyar al Club STEM. Te compartimos las formas de aportar y el impacto de cada una.',
  general: '¡Hola {nombre}! Gracias por escribirnos al Club STEM. Un miembro del equipo te contactará muy pronto.',
};

// Quita tildes/diéresis para que la segmentación no dependa de cómo escriban.
// Se usa el rango de marcas diacríticas combinantes en escapes Unicode
// (evita caracteres invisibles en el código fuente).
const sinTildes = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '');

// Equivalente al str.title() de Python: pone en mayúscula toda letra que venga
// después de un carácter no alfabético. Importa para apellidos reales como
// D'Angelo o Ana-María, donde partir solo por espacios daría "D'angelo".
//
// Se normaliza a NFC primero porque "í" puede llegar precompuesta o como
// "i" + tilde combinante (macOS envía esta última): sin normalizar, la tilde
// cuenta como separador y "maría" termina como "MaríA".
const titleCase = (s) =>
  s.normalize('NFC').toLowerCase()
    .replace(/(^|[^\p{L}\p{M}])(\p{L})/gu, (_, prev, letra) =>
      prev + letra.toUpperCase());

// ── Nodo 1: normalizar ──
function normalizarLead(crudo) {
  const nombre = titleCase(String(crudo.nombre || '').trim());
  const email = String(crudo.email || '').trim().toLowerCase();
  let telefono = String(crudo.telefono || '').replace(/[^\d+]/g, '');
  if (telefono.startsWith('+51')) {
    // ya está en formato E.164
  } else if (telefono.startsWith('51') && telefono.length === 11) {
    telefono = '+' + telefono;
  } else if (telefono.length === 9) {
    telefono = '+51' + telefono;
  }
  return {
    nombre,
    email,
    telefono,
    mensaje: String(crudo.mensaje || '').replace(/\s+/g, ' ').trim(),
    canal: String(crudo.canal || 'web').trim().toLowerCase() || 'web',
    fecha: crudo.fecha || new Date().toISOString().slice(0, 19),
  };
}

// ── Nodo 2: validar ──
function validarLead(lead) {
  if (!lead.nombre) return { ok: false, motivo: 'sin nombre' };
  const emailOk = /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(lead.email);
  const telOk = /^\+51\d{9}$/.test(lead.telefono);
  if (!emailOk && !telOk) {
    return { ok: false, motivo: 'sin email ni teléfono válidos' };
  }
  return { ok: true, motivo: 'ok' };
}

// ── Nodo 3: deduplicar ──
function esDuplicado(lead, crm) {
  return crm.some((f) =>
    (lead.email && lead.email === f.email) ||
    (lead.telefono && lead.telefono === f.telefono));
}

// ── Nodo 4: segmentar ──
function segmentar(lead) {
  const texto = sinTildes((lead.mensaje || '').toLowerCase());
  for (const seg of ['donacion', 'voluntariado', 'talleres']) {
    if (KEYWORDS[seg].some((k) => texto.includes(k))) return seg;
  }
  return 'general';
}

// ── Ejecución ──
const store = $getWorkflowStaticData('global');
if (!Array.isArray(store.crm)) store.crm = [];

const salida = [];

for (const item of $input.all()) {
  const crudo = item.json.body || item.json;   // el webhook entrega el payload en .body
  const lead = normalizarLead(crudo);

  const v = validarLead(lead);
  if (!v.ok) {
    salida.push({ json: { resultado: 'invalido', motivo: v.motivo, lead } });
    continue;
  }

  if (esDuplicado(lead, store.crm)) {
    salida.push({ json: { resultado: 'duplicado', lead } });
    continue;
  }

  const segmento = segmentar(lead);
  const filaCrm = Object.assign({}, lead, { segmento, estado: 'nuevo' });
  store.crm.push(filaCrm);

  salida.push({
    json: {
      resultado: 'nuevo',
      segmento,
      lead,
      crm_fila: filaCrm,
      crm_total: store.crm.length,
      newsletter: {
        email: lead.email,
        tag: segmento,
        accion: lead.email ? 'suscribir' : 'omitir',
      },
      email_bienvenida: BIENVENIDA[segmento].replace('{nombre}', lead.nombre.split(' ')[0]),
      notificacion_equipo:
        '🔔 Nuevo lead [' + segmento + '] ' + lead.nombre +
        ' (' + lead.canal + ') — ' + (lead.email || lead.telefono),
    },
  });
}

return salida;
