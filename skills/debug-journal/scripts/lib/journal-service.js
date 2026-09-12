const { canTransition } = require('./fsm');
const schema = require('./schema');
const { normalizePath } = require('./paths');
const { journalExists, loadJournal, saveJournalTransactional } = require('./journal-store');
const { withIndex, toIndexEntry } = require('./index-service');
const { slugify, todayISO, isValidISODate } = require('./utils');

function warn(msg) { console.error(`Warning: ${msg}`); }

function generateUniqueId(title, date) {
  const base = slugify(title);
  let id = `${date}_${base}`, n = 2;
  while (journalExists(id)) id = `${date}_${base}-${n++}`;
  return id;
}

function detectsRegressionCycle(selfId, targetId) {
  let current = targetId, hops = 0;
  while (current && hops < 200) {
    if (current === selfId) return true;
    let j; try { j = loadJournal(current); } catch { return false; }
    current = j.regression_of; hops++;
  }
  return false;
}
function validateRegressionOf(selfId, regressionOf) {
  if (!regressionOf) return null;
  if (regressionOf === selfId) throw new Error('a journal cannot be regression_of itself');
  if (!journalExists(regressionOf)) throw new Error(`regression_of references unknown journal "${regressionOf}" — check the id with search.js`);
  if (detectsRegressionCycle(selfId, regressionOf)) throw new Error(`setting regression_of to "${regressionOf}" would create a circular regression chain (A -> B -> ... -> A)`);
  return regressionOf;
}
function validateRelatedBugs(selfId, ids) {
  const unique = [...new Set(ids)].filter(id => id !== selfId);
  if (unique.length !== ids.length) warn(`removed ${ids.length - unique.length} duplicate/self-referencing related_bugs entr${ids.length - unique.length === 1 ? 'y' : 'ies'}`);
  const missing = unique.filter(id => !journalExists(id));
  if (missing.length) throw new Error(`related_bugs references unknown journal(s): ${missing.join(', ')}`);
  return unique;
}
function buildFixFiles(specs) { return schema.dedupeFixFiles(specs.map(s => schema.validateFixFileEntry({ ...s, path: normalizePath(s.path) }, warn)).filter(Boolean)); }
function buildEvidence(entries) { return schema.dedupeEvidence(entries.map(e => schema.validateEvidenceEntry(e, warn)).filter(Boolean)); }
function upsertInIndexArray(index, journal) { const entry = toIndexEntry(journal); const i = index.findIndex(e => e.id === journal.id); if (i >= 0) index[i] = entry; else index.push(entry); return index; }
function commitJournal(index, journal) {
  schema.validateJournalRecord(journal);
  const updatedIndex = upsertInIndexArray(index, journal);
  const rollback = saveJournalTransactional(journal);
  return { index: updatedIndex, rollback };
}

function createJournal(fields) {
  const title = schema.validateTitle(fields.title);
  const category = schema.validateCategory(fields.category || 'rtl');
  const severity = schema.validateSeverity(fields.severity || 'major');
  const tags = schema.normalizeTags(fields.tags || []);
  const evidence = buildEvidence(fields.evidence || []);
  if (fields.date_opened && !isValidISODate(fields.date_opened)) throw new Error(`invalid date_opened "${fields.date_opened}" — expected a real calendar date YYYY-MM-DD`);
  const date = fields.date_opened || todayISO();
  let created;
  withIndex(index => {
    const id = generateUniqueId(title, date);
    validateRegressionOf(id, fields.regression_of || null);
    const related_bugs = validateRelatedBugs(id, fields.related_bugs || []);
    const journal = {
      id, schema_version: schema.SCHEMA_VERSION, title,
      date_opened: date, date_predicted: null, date_confirmed: null, date_closed: null,
      resolution: '', category, severity, status: 'investigating', workflow_state: 'OPEN',
      status_history: [{ status: 'investigating', workflow_state: 'OPEN', date, note: 'created' }],
      test_name: fields.test_name || '', seed: fields.seed || '', failure_signature: fields.failure_signature || '',
      symptom: fields.symptom || '', hypothesis: '', root_cause: '', evidence,
      fix: { description: '', files: [], commit: '', applied_date: '' }, owner: fields.owner || '',
      regression_of: fields.regression_of || null, related_bugs, tags
    };
    created = journal;
    return commitJournal(index, journal);
  });
  return created;
}

function updateJournal(id, changes) {
  let updated;
  withIndex(index => {
    if (!journalExists(id)) throw new Error(`No journal found with id "${id}". Run rebuild-index.js if you believe it should exist.`);
    const journal = loadJournal(id);
    const today = todayISO();

    // --reopen without --status defaults to investigating.
    const requestedStatus = changes.status || (changes.reopen ? 'investigating' : null);
    if (requestedStatus) {
      const target = schema.validateStatus(requestedStatus);
      const result = canTransition(journal.status, target, { reopen: !!changes.reopen, workflowState: journal.workflow_state });
      if (!result.ok) throw new Error(result.reason);

      if (result.reopened) {
        // Top-level lifecycle timestamps describe the CURRENT investigation
        // cycle. Prior cycle chronology remains in status_history.
        journal.date_closed = null;
        journal.date_predicted = null;
        journal.date_confirmed = null;
        journal.resolution = '';
        journal.workflow_state = 'OPEN';
        journal.status = target;
        if (target === 'predicted') journal.date_predicted = today;
        journal.status_history.push({ status: target, workflow_state: 'OPEN', date: today, note: 'reopened' });
      } else if (target !== journal.status) {
        journal.status = target;
        if (target === 'predicted' && !journal.date_predicted) journal.date_predicted = today;
        if (target === 'confirmed') {
          if (!journal.date_confirmed) journal.date_confirmed = today;
          journal.date_closed = today;
          journal.workflow_state = 'CLOSED';
        } else if (target === 'retracted') {
          journal.date_closed = today;
          journal.workflow_state = 'CLOSED';
        }
        journal.status_history.push({ status: target, workflow_state: journal.workflow_state, date: today });
      }
    }

    if (changes.close) {
      if (journal.workflow_state === 'CLOSED') {
        if (changes.resolution) journal.resolution = changes.resolution;
      } else {
        if (!['confirmed', 'retracted'].includes(journal.status) && !changes.resolution) {
          throw new Error('closing an open investigating/predicted journal requires --resolution "<reason>" (e.g. "not-a-bug", "duplicate", "wont-fix")');
        }
        journal.workflow_state = 'CLOSED';
        journal.date_closed = today;
        if (changes.resolution) journal.resolution = changes.resolution;
        journal.status_history.push({ status: journal.status, workflow_state: 'CLOSED', date: today, note: `closed${journal.resolution ? `: ${journal.resolution}` : ''}` });
      }
    }

    if (changes.severity) journal.severity = schema.validateSeverity(changes.severity);
    if (changes.hypothesis) journal.hypothesis = changes.hypothesis;
    if (changes.root_cause) journal.root_cause = changes.root_cause;
    if (changes.symptom) journal.symptom = changes.symptom;
    if (changes.owner) journal.owner = changes.owner;
    if (changes.test_name) journal.test_name = changes.test_name;
    if (changes.seed) journal.seed = changes.seed;
    if (changes.failure_signature) journal.failure_signature = changes.failure_signature;
    if (changes.regression_of) journal.regression_of = validateRegressionOf(id, changes.regression_of);
    if (changes.related_bugs && changes.related_bugs.length) journal.related_bugs = validateRelatedBugs(id, [...journal.related_bugs, ...changes.related_bugs]);
    if (changes.tags && changes.tags.length) journal.tags = schema.normalizeTags([...journal.tags, ...changes.tags]);
    if (changes.evidence && changes.evidence.length) journal.evidence = schema.dedupeEvidence([...journal.evidence, ...buildEvidence(changes.evidence)]);
    if (changes.fix_description) journal.fix.description = changes.fix_description;
    if (changes.fix_commit) journal.fix.commit = changes.fix_commit;
    if (changes.fix_applied_date) {
      if (!isValidISODate(changes.fix_applied_date)) throw new Error(`invalid --fix-applied-date "${changes.fix_applied_date}" — expected a real calendar date YYYY-MM-DD`);
      journal.fix.applied_date = changes.fix_applied_date;
    }
    if (changes.fix_files && changes.fix_files.length) journal.fix.files = schema.dedupeFixFiles([...journal.fix.files, ...buildFixFiles(changes.fix_files)]);

    updated = journal;
    return commitJournal(index, journal);
  });
  return updated;
}

function importJournal(fields) {
  const title = schema.validateTitle(fields.title);
  const category = schema.validateCategory(fields.category || 'rtl');
  const severity = schema.validateSeverity(fields.severity || 'major');
  const status = schema.validateStatus(fields.status || 'investigating');
  const tags = schema.normalizeTags(fields.tags || []);
  ['date_opened', 'date_predicted', 'date_confirmed', 'date_closed'].forEach(k => { if (fields[k] && !isValidISODate(fields[k])) throw new Error(`invalid ${k} "${fields[k]}" — expected a real calendar date YYYY-MM-DD`); });
  if (fields.fix_applied_date && !isValidISODate(fields.fix_applied_date)) throw new Error(`invalid fix_applied_date "${fields.fix_applied_date}" — expected a real calendar date YYYY-MM-DD`);

  const date_opened = fields.date_opened || todayISO();
  // Do not invent a prediction for retracted imports. Only predicted/confirmed
  // imply that a hypothesis was actually recorded.
  const date_predicted = fields.date_predicted || (['predicted', 'confirmed'].includes(status) ? date_opened : null);
  const date_confirmed = fields.date_confirmed || (status === 'confirmed' ? (date_predicted || date_opened) : null);
  const inferredClosed = ['confirmed', 'retracted'].includes(status) || !!fields.date_closed || !!fields.resolution;
  const workflow_state = inferredClosed ? 'CLOSED' : 'OPEN';
  const date_closed = fields.date_closed || (workflow_state === 'CLOSED' ? (date_confirmed || date_predicted || date_opened) : null);

  let created;
  withIndex(index => {
    const id = generateUniqueId(title, date_opened);
    validateRegressionOf(id, fields.regression_of || null);
    const journal = {
      id, schema_version: schema.SCHEMA_VERSION, title, date_opened, date_predicted, date_confirmed, date_closed,
      resolution: fields.resolution || '', category, severity, status, workflow_state,
      status_history: [{ status, workflow_state, date: date_opened, note: 'imported' }],
      test_name: fields.test_name || '', seed: fields.seed || '', failure_signature: fields.failure_signature || '',
      symptom: fields.symptom || '', hypothesis: fields.hypothesis || '', root_cause: fields.root_cause || '', evidence: [],
      fix: { description: fields.fix_description || '', files: buildFixFiles(fields.fix_files || []), commit: fields.fix_commit || '', applied_date: fields.fix_applied_date || '' },
      owner: fields.owner || '', regression_of: fields.regression_of || null, related_bugs: [], tags
    };
    created = journal;
    return commitJournal(index, journal);
  });
  return created;
}

function contentFingerprint(fields) {
  const norm = s => String(s || '').toLowerCase().trim().replace(/\s+/g, ' ');
  return [norm(fields.title), norm(fields.category), norm(fields.test_name), norm(fields.symptom)].join('||');
}

module.exports = { createJournal, updateJournal, importJournal, contentFingerprint, generateUniqueId, validateRegressionOf, validateRelatedBugs };
