// Ejecuta el código del nodo Code de n8n fuera de n8n, simulando sus globals.
// Uso:  node tests/correr_nodo_js.mjs <ruta_csv>
// Salida: JSON por stdout con el resultado de cada lead (para comparar con Python).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const jsCode = readFileSync(join(ROOT, 'workflows', 'src', 'procesar_lead.js'), 'utf8');

// --- CSV mínimo (sin dependencias) ---
function parseCSV(texto) {
  const filas = [];
  let campo = '', fila = [], enComillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (enComillas) {
      if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
      else if (c === '"') enComillas = false;
      else campo += c;
    } else if (c === '"') enComillas = true;
    else if (c === ',') { fila.push(campo); campo = ''; }
    else if (c === '\n') { fila.push(campo); filas.push(fila); fila = []; campo = ''; }
    else if (c !== '\r') campo += c;
  }
  if (campo || fila.length) { fila.push(campo); filas.push(fila); }
  const [cab, ...resto] = filas.filter((f) => f.length > 1);
  return resto.map((f) => Object.fromEntries(cab.map((k, i) => [k, f[i] ?? ''])));
}

// --- Simulación de los globals de n8n ---
const staticData = {};
const $getWorkflowStaticData = () => staticData;

const csvPath = process.argv[2] || join(ROOT, 'data', 'leads_ficticios.csv');
const registros = parseCSV(readFileSync(csvPath, 'utf8'));

// El nodo Code corre una vez con TODOS los items; aquí replicamos eso.
const $input = { all: () => registros.map((json) => ({ json })) };

// El código del nodo termina en `return`, así que se envuelve en una función.
const ejecutarNodo = new Function('$input', '$getWorkflowStaticData', jsCode);
const salida = ejecutarNodo($input, $getWorkflowStaticData);

// Solo los campos comparables con la implementación Python.
const comparable = salida.map((s) => ({
  resultado: s.json.resultado,
  segmento: s.json.segmento ?? null,
  email: (s.json.crm_fila ?? s.json.lead).email,
  telefono: (s.json.crm_fila ?? s.json.lead).telefono,
  nombre: (s.json.crm_fila ?? s.json.lead).nombre,
}));

process.stdout.write(JSON.stringify(comparable));
