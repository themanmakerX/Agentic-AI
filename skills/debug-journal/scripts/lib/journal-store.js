const fs = require('fs');
const path = require('path');
const { atomicWriteFile } = require('./atomic');
const schema = require('./schema');

const ROOT = path.resolve(__dirname, '..', '..');
const JOURNALS_DIR = path.join(ROOT, 'journals');
const INDEX_PATH = path.join(ROOT, 'index.json');
const INDEX_LOCK_PATH = path.join(ROOT, '.index.lock');

function ensureDirs() { if (!fs.existsSync(JOURNALS_DIR)) fs.mkdirSync(JOURNALS_DIR, { recursive: true }); }
function journalPath(id, ext) { return path.join(JOURNALS_DIR, `${id}.${ext}`); }
function journalExists(id) { return fs.existsSync(journalPath(id, 'json')); }
function listJournalIds() { ensureDirs(); return fs.readdirSync(JOURNALS_DIR).filter(f => f.endsWith('.json')).map(f => f.replace(/\.json$/, '')); }

function loadJournal(id) {
  const p = journalPath(id, 'json');
  if (!fs.existsSync(p)) throw new Error(`No journal found with id "${id}" (checked ${p})`);
  let journal;
  try { journal = JSON.parse(fs.readFileSync(p, 'utf8')); }
  catch (e) { throw new Error(`Journal file ${p} is corrupted (invalid JSON): ${e.message}`); }
  return migrate(journal);
}

function migrate(journal) {
  if (!journal || typeof journal !== 'object' || Array.isArray(journal)) throw new Error('journal root must be a JSON object');
  const rawVersion = journal.schema_version === undefined ? 1 : Number(journal.schema_version);
  if (!Number.isInteger(rawVersion) || rawVersion < 1) throw new Error(`invalid schema_version "${journal.schema_version}"`);
  if (rawVersion > schema.SCHEMA_VERSION) throw new Error(`journal schema_version ${rawVersion} is newer than this tool supports (${schema.SCHEMA_VERSION}); upgrade the skill instead of downgrading the journal`);

  const j = JSON.parse(JSON.stringify(journal));
  if (j.severity === undefined) j.severity = 'major';
  if (j.date_predicted === undefined) j.date_predicted = null;
  if (j.date_confirmed === undefined) j.date_confirmed = null;
  if (j.date_closed === undefined) j.date_closed = null;
  if (j.regression_of === undefined) j.regression_of = null;
  if (j.related_bugs === undefined) j.related_bugs = [];
  if (j.evidence === undefined) j.evidence = [];
  if (j.tags === undefined) j.tags = [];
  if (j.status === undefined) j.status = 'investigating';
  if (j.status_history === undefined) j.status_history = [{ status: j.status, date: j.date_opened, note: 'migrated (no prior history recorded)' }];
  if (j.resolution === undefined) j.resolution = '';
  if (!j.fix) j.fix = { description: '', files: [], commit: '', applied_date: '' };
  if (!Array.isArray(j.fix.files)) j.fix.files = [];

  // v3 separates diagnosis from whether the workflow is open/closed.
  if (j.workflow_state === undefined) {
    j.workflow_state = (j.date_closed || ['confirmed', 'retracted'].includes(j.status)) ? 'CLOSED' : 'OPEN';
    if (j.workflow_state === 'CLOSED' && !j.date_closed) {
      j.date_closed = j.date_confirmed || j.date_predicted || j.date_opened;
    }
  }
  j.schema_version = schema.SCHEMA_VERSION;
  return schema.validateJournalRecord(j);
}

function renderMarkdown(j) {
  const lines = [`# ${j.title}`, '', `**ID:** \`${j.id}\`  `, `**Category:** ${j.category}  `, `**Status:** ${j.status}  `, `**Workflow:** ${j.workflow_state}  `, `**Severity:** ${j.severity}  `, `**Opened:** ${j.date_opened}  `];
  if (j.date_predicted) lines.push(`**Hypothesis logged:** ${j.date_predicted}  `);
  if (j.date_confirmed) lines.push(`**Confirmed:** ${j.date_confirmed}  `);
  if (j.date_closed) lines.push(`**Closed:** ${j.date_closed}${j.resolution ? ' (' + j.resolution + ')' : ''}  `);
  if (j.owner) lines.push(`**Owner:** ${j.owner}  `);
  if (j.regression_of) lines.push(`**Regression of:** ${j.regression_of}  `);
  lines.push('');
  if (j.test_name || j.seed || j.failure_signature) {
    lines.push('## Failure Info');
    if (j.test_name) lines.push(`- **Test:** ${j.test_name}`);
    if (j.seed) lines.push(`- **Seed:** ${j.seed}`);
    if (j.failure_signature) lines.push(`- **Signature:** \`${j.failure_signature}\``);
    lines.push('');
  }
  lines.push('## Symptom', j.symptom || '_(not filled in)_', '');
  if (j.hypothesis) lines.push('## Hypothesis', j.hypothesis, '');
  if (j.root_cause) lines.push('## Root Cause', j.root_cause, '');
  if (j.evidence && j.evidence.length) {
    lines.push('## Evidence');
    j.evidence.forEach(e => {
      if (e.type === 'log') lines.push(`- **[log]** \`${e.file}${e.line ? ':' + e.line : ''}\`${e.note ? ' — ' + e.note : ''}`);
      else if (e.type === 'waveform') lines.push(`- **[waveform]** \`${e.path}\`${e.timestamp ? ' @ ' + e.timestamp : ''}${e.note ? ' — ' + e.note : ''}`);
      else lines.push(`- ${e.text || JSON.stringify(e)}`);
    });
    lines.push('');
  }
  if (j.fix && (j.fix.description || (j.fix.files && j.fix.files.length))) {
    lines.push('## Fix');
    if (j.fix.description) lines.push(j.fix.description);
    if (j.fix.files && j.fix.files.length) {
      lines.push('', '**Files changed:**');
      j.fix.files.forEach(f => lines.push(`- \`${f.path}${f.lines ? ':' + f.lines : ''}\`${f.note ? ' — ' + f.note : ''}`));
    }
    if (j.fix.commit) lines.push(`\n**Commit:** \`${j.fix.commit}\``);
    if (j.fix.applied_date) lines.push(`**Applied:** ${j.fix.applied_date}`);
    lines.push('');
  }
  if (j.related_bugs && j.related_bugs.length) { lines.push('## Related Bugs'); j.related_bugs.forEach(id => lines.push(`- ${id}`)); lines.push(''); }
  if (j.status_history && j.status_history.length) { lines.push('## Status History'); j.status_history.forEach(h => lines.push(`- ${h.date}: ${h.status}${h.workflow_state ? ` [${h.workflow_state}]` : ''}${h.note ? ' — ' + h.note : ''}`)); lines.push(''); }
  if (j.tags && j.tags.length) lines.push(`**Tags:** ${j.tags.map(t => `\`${t}\``).join(', ')}`, '');
  return lines.join('\n');
}

function snapshotFile(p) { return fs.existsSync(p) ? fs.readFileSync(p) : null; }
function restoreFile(p, snapshot) {
  if (snapshot === null) { try { fs.unlinkSync(p); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
  else atomicWriteFile(p, snapshot);
}

// Writes JSON + Markdown as one recoverable unit and returns a rollback hook.
// withIndex() calls that hook if the subsequent index commit fails.
function saveJournalTransactional(journal) {
  ensureDirs();
  schema.validateJournalRecord(journal);
  const jsonPath = journalPath(journal.id, 'json');
  const mdPath = journalPath(journal.id, 'md');
  const oldJson = snapshotFile(jsonPath), oldMd = snapshotFile(mdPath);
  try {
    atomicWriteFile(jsonPath, JSON.stringify(journal, null, 2) + '\n');
    atomicWriteFile(mdPath, renderMarkdown(journal));
  } catch (e) {
    try { restoreFile(jsonPath, oldJson); restoreFile(mdPath, oldMd); } catch (r) { e.message += `; rollback also failed: ${r.message}`; }
    throw e;
  }
  return () => { restoreFile(jsonPath, oldJson); restoreFile(mdPath, oldMd); };
}

function saveJournal(journal) { saveJournalTransactional(journal); }
function loadAllJournalsTolerant(onError) {
  return listJournalIds().map(id => { try { return loadJournal(id); } catch (e) { onError ? onError(id, e) : console.error(`Warning: skipping unreadable journal "${id}": ${e.message}`); return null; } }).filter(Boolean);
}

module.exports = { ROOT, JOURNALS_DIR, INDEX_PATH, INDEX_LOCK_PATH, ensureDirs, journalPath, journalExists, listJournalIds, loadJournal, migrate, saveJournal, saveJournalTransactional, renderMarkdown, loadAllJournalsTolerant };
