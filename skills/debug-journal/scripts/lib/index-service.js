const fs = require('fs');
const path = require('path');
const { atomicWriteFile } = require('./atomic');
const { withLock } = require('./lock');
const { INDEX_PATH, INDEX_LOCK_PATH, JOURNALS_DIR, ensureDirs, listJournalIds, loadJournal } = require('./journal-store');

function toIndexEntry(j) {
  return {
    id: j.id, title: j.title, category: j.category, status: j.status,
    workflow_state: j.workflow_state, resolution: j.resolution || '',
    severity: j.severity || '', date_opened: j.date_opened,
    date_predicted: j.date_predicted || null, date_confirmed: j.date_confirmed || null,
    date_closed: j.date_closed || null, test_name: j.test_name || '', seed: j.seed || '',
    tags: j.tags || [], fix_files: (j.fix && j.fix.files ? j.fix.files.map(f => ({ path: f.path, lines: f.lines || '' })) : []),
    symptom: j.symptom || '', failure_signature: j.failure_signature || '', regression_of: j.regression_of || null
  };
}

function validateIndexShape(index) {
  if (!Array.isArray(index)) return false;
  const ids = new Set();
  for (const e of index) {
    if (!e || typeof e !== 'object' || Array.isArray(e) || typeof e.id !== 'string' || !e.id || ids.has(e.id)) return false;
    if (!Array.isArray(e.tags) || !Array.isArray(e.fix_files)) return false;
    if (!['OPEN', 'CLOSED'].includes(e.workflow_state)) return false;
    ids.add(e.id);
  }
  return true;
}

function rebuildIndexUnlocked() {
  const journals = [];
  const errors = [];
  for (const id of listJournalIds()) {
    try { journals.push(loadJournal(id)); }
    catch (e) { errors.push(`${id}: ${e.message}`); }
  }
  if (errors.length) {
    throw new Error(`Cannot rebuild index safely: ${errors.length} journal file(s) are unreadable. No partial index was written.\n- ${errors.join('\n- ')}`);
  }
  const index = journals.map(toIndexEntry);
  atomicWriteFile(INDEX_PATH, JSON.stringify(index, null, 2) + '\n');
  return index;
}

function indexIsStale(index) {
  let indexStat;
  try { indexStat = fs.statSync(INDEX_PATH); } catch { return true; }
  const ids = listJournalIds();
  if (ids.length !== index.length) return true;
  const set = new Set(index.map(e => e.id));
  if (ids.some(id => !set.has(id))) return true;
  for (const id of ids) {
    try {
      const st = fs.statSync(path.join(JOURNALS_DIR, `${id}.json`));
      if (st.mtimeMs > indexStat.mtimeMs + 1) return true;
    } catch { return true; }
  }
  return false;
}

function loadIndexUnlocked() {
  ensureDirs();
  if (!fs.existsSync(INDEX_PATH)) return rebuildIndexUnlocked();
  let index;
  try { index = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8')); }
  catch (e) { console.error(`Warning: index.json is corrupted (${e.message}). Rebuilding from journals/*.json ...`); return rebuildIndexUnlocked(); }
  if (!validateIndexShape(index)) { console.error('Warning: index.json has an invalid structure. Rebuilding from journals/*.json ...'); return rebuildIndexUnlocked(); }
  if (indexIsStale(index)) { console.error('Warning: index.json is stale relative to journals/*.json. Rebuilding ...'); return rebuildIndexUnlocked(); }
  return index;
}

function loadIndex() { return loadIndexUnlocked(); }
function rebuildIndex() { return withLock(INDEX_LOCK_PATH, rebuildIndexUnlocked); }

// Callback may return either an array or { index, rollback }. If index commit
// fails, rollback restores journal JSON/Markdown to their pre-transaction state.
function withIndex(fn) {
  return withLock(INDEX_LOCK_PATH, () => {
    const index = loadIndexUnlocked();
    const result = fn(index);
    const updated = Array.isArray(result) ? result : result && result.index;
    const rollback = result && !Array.isArray(result) && typeof result.rollback === 'function' ? result.rollback : null;
    if (!Array.isArray(updated)) throw new Error('withIndex callback must return an index array or {index, rollback}');
    try {
      atomicWriteFile(INDEX_PATH, JSON.stringify(updated, null, 2) + '\n');
    } catch (e) {
      if (rollback) {
        try { rollback(); } catch (r) { e.message += `; journal rollback also failed: ${r.message}`; }
      }
      throw e;
    }
    return updated;
  });
}

function upsertIndexEntry(journal) {
  return withIndex(index => { const entry = toIndexEntry(journal); const i = index.findIndex(e => e.id === journal.id); if (i >= 0) index[i] = entry; else index.push(entry); return index; });
}

module.exports = { loadIndex, rebuildIndex, withIndex, upsertIndexEntry, toIndexEntry, validateIndexShape, indexIsStale };
