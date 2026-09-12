const { isValidISODate } = require('./utils');

const SCHEMA_VERSION = 3;
const CATEGORIES = ['rtl', 'testbench', 'sequence', 'spec', 'tool', 'infra'];
const SEVERITIES = ['blocker', 'major', 'minor'];
const STATUSES = ['investigating', 'predicted', 'confirmed', 'retracted'];
const WORKFLOW_STATES = ['OPEN', 'CLOSED'];
const MAX_TITLE_LENGTH = 200;

function validateTitle(title) {
  if (typeof title !== 'string' || !title.trim()) throw new Error('title must be a non-empty string');
  const t = title.trim();
  if (t.length > MAX_TITLE_LENGTH) throw new Error(`title exceeds max length of ${MAX_TITLE_LENGTH} characters (got ${t.length})`);
  return t;
}
function validateCategory(c) { if (!CATEGORIES.includes(c)) throw new Error(`category must be one of ${CATEGORIES.join(', ')} (got "${c}")`); return c; }
function validateSeverity(s) { if (!SEVERITIES.includes(s)) throw new Error(`severity must be one of ${SEVERITIES.join(', ')} (got "${s}")`); return s; }
function validateStatus(s) { if (!STATUSES.includes(s)) throw new Error(`status must be one of ${STATUSES.join(', ')} (got "${s}")`); return s; }
function validateWorkflowState(s) { if (!WORKFLOW_STATES.includes(s)) throw new Error(`workflow_state must be OPEN or CLOSED (got "${s}")`); return s; }

function validateLines(spec) {
  if (spec === undefined || spec === null || String(spec).trim() === '') return '';
  const s = String(spec).trim();
  const range = s.match(/^(\d+)\s*-\s*(\d+)$/);
  const single = s.match(/^(\d+)$/);
  if (!range && !single) throw new Error(`invalid line spec "${s}" — expected a line number ("142") or range ("142-158")`);
  const [start, end] = range ? [parseInt(range[1], 10), parseInt(range[2], 10)] : [parseInt(single[1], 10), parseInt(single[1], 10)];
  if (start < 1 || end < 1) throw new Error(`invalid line spec "${s}" — line numbers start at 1`);
  if (start > end) throw new Error(`invalid line spec "${s}" — start must be <= end (did you mean "${end}-${start}"?)`);
  return s;
}

function normalizeTag(t) { return String(t).trim().toLowerCase(); }
function normalizeTags(tags) {
  const seen = new Set(), out = [];
  (tags || []).forEach(t => { const n = normalizeTag(t); if (n && !seen.has(n)) { seen.add(n); out.push(n); } });
  return out;
}

function validateFixFileEntry(entry, warn) {
  const p = String(entry.path || '').trim();
  if (!p) { warn && warn('skipping fix-file entry with empty path'); return null; }
  return { path: p, lines: validateLines(entry.lines || ''), note: String(entry.note || '').trim() };
}
function validateEvidenceEntry(entry, warn) {
  if (entry.type === 'log') {
    const file = String(entry.file || '').trim();
    if (!file) { warn && warn('skipping log evidence with empty file'); return null; }
    return { type: 'log', file, line: validateLines(entry.line || ''), note: String(entry.note || '').trim() };
  }
  if (entry.type === 'waveform') {
    const p = String(entry.path || '').trim();
    if (!p) { warn && warn('skipping waveform evidence with empty path'); return null; }
    return { type: 'waveform', path: p, timestamp: String(entry.timestamp || '').trim(), note: String(entry.note || '').trim() };
  }
  const text = String(entry.text || '').trim();
  if (!text) { warn && warn('skipping empty note evidence'); return null; }
  return { type: 'note', text };
}

function dedupeFixFiles(files) {
  const seen = new Set(), out = [];
  files.forEach(f => { const key = `${f.path}|${f.lines}`; if (!seen.has(key)) { seen.add(key); out.push(f); } });
  return out;
}
function dedupeEvidence(evidence) {
  const seen = new Set(), out = [];
  evidence.forEach(e => { const key = JSON.stringify(e); if (!seen.has(key)) { seen.add(key); out.push(e); } });
  return out;
}

function validateDateOrder(j) {
  const order = ['date_opened', 'date_predicted', 'date_confirmed', 'date_closed'];
  for (const k of order) if (j[k] && !isValidISODate(j[k])) throw new Error(`invalid ${k} "${j[k]}" — expected a real calendar date YYYY-MM-DD`);
  const present = order.filter(k => j[k]);
  for (let i = 1; i < present.length; i++) {
    if (j[present[i - 1]] > j[present[i]]) throw new Error(`lifecycle date order violated: ${present[i - 1]}=${j[present[i - 1]]} is after ${present[i]}=${j[present[i]]}`);
  }
  if (j.workflow_state === 'OPEN' && j.date_closed) throw new Error('workflow_state OPEN cannot have date_closed set');
  if (j.workflow_state === 'CLOSED' && !j.date_closed) throw new Error('workflow_state CLOSED requires date_closed');
  if (j.status === 'confirmed' && !j.date_confirmed) throw new Error('confirmed status requires date_confirmed');
}

function validateJournalRecord(j) {
  if (!j || typeof j !== 'object' || Array.isArray(j)) throw new Error('journal must be a JSON object');
  if (j.schema_version !== SCHEMA_VERSION) throw new Error(`journal schema_version must be ${SCHEMA_VERSION} after migration`);
  if (typeof j.id !== 'string' || !j.id.trim()) throw new Error('journal id must be a non-empty string');
  validateTitle(j.title);
  validateCategory(j.category);
  validateSeverity(j.severity);
  validateStatus(j.status);
  validateWorkflowState(j.workflow_state);
  if (!Array.isArray(j.status_history)) throw new Error('status_history must be an array');
  if (!Array.isArray(j.related_bugs)) throw new Error('related_bugs must be an array');
  if (!Array.isArray(j.evidence)) throw new Error('evidence must be an array');
  if (!Array.isArray(j.tags)) throw new Error('tags must be an array');
  if (!j.fix || typeof j.fix !== 'object' || !Array.isArray(j.fix.files)) throw new Error('fix.files must be an array');
  validateDateOrder(j);
  return j;
}

module.exports = {
  SCHEMA_VERSION, CATEGORIES, SEVERITIES, STATUSES, WORKFLOW_STATES, MAX_TITLE_LENGTH,
  validateTitle, validateCategory, validateSeverity, validateStatus, validateWorkflowState, validateLines,
  normalizeTag, normalizeTags, validateFixFileEntry, validateEvidenceEntry, dedupeFixFiles, dedupeEvidence,
  validateDateOrder, validateJournalRecord
};
