#!/usr/bin/env node
/**
 * Bulk-import journals from a CSV export (e.g. Jira or spreadsheet export).
 *
 * Recognized header columns (case-insensitive; only "title" is required):
 *   title, category, severity, status, test_name, seed, failure_signature,
 *   symptom, hypothesis, root_cause, owner, tags, regression_of,
 *   fix_description, fix_files, fix_commit,
 *   date_opened, date_predicted, date_confirmed, date_closed, resolution
 *
 * Dates (YYYY-MM-DD) are used as-is if provided, so historical bugs keep
 * their real dates instead of getting today's date. Chronology and other
 * schema rules are still validated per row.
 *
 * Since this is CSV, use semicolons (not commas) inside a cell for multiple
 * tags or fix files:
 *   tags column:      axi;hang;fsm
 *   fix_files column: rtl/axi_wr_fsm.sv:142-158;tb/axi_scoreboard.sv
 * (fix_files "path:lines" parsing is drive-letter-safe, so
 *  "C:\repo\foo.sv:10-20" parses correctly on Windows-exported paths.)
 *
 * Usage:
 *   node import.js --file past_bugs.csv --dry-run   # preview first
 *   node import.js --file past_bugs.csv
 */
const fs = require('fs');
const { importJournal, contentFingerprint } = require('./lib/journal-service');
const { loadAllJournalsTolerant } = require('./lib/journal-store');
const { parseColonSpec } = require('./lib/paths');
const { parseArgs, fail } = require('./lib/utils');

const args = parseArgs(process.argv.slice(2));
if (!args.file) fail('--file <path.csv> is required');
if (!fs.existsSync(args.file)) fail(`file not found: ${args.file}`);

const REQUIRED_COLUMNS = ['title'];
const KNOWN_COLUMNS = [
  'title', 'category', 'severity', 'status', 'test_name', 'seed', 'failure_signature',
  'symptom', 'hypothesis', 'root_cause', 'owner', 'tags', 'regression_of',
  'fix_description', 'fix_files', 'fix_commit',
  'date_opened', 'date_predicted', 'date_confirmed', 'date_closed', 'resolution'
];

function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') { inQuotes = false; }
      else field += c;
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else if (c === '\r') { /* skip */ }
      else field += c;
    }
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows.filter(r => r.some(c => c.trim() !== ''));
}

let raw = fs.readFileSync(args.file, 'utf8');
if (raw.charCodeAt(0) === 0xFEFF) raw = raw.slice(1); // strip UTF-8 BOM

const rows = parseCSV(raw);
if (rows.length < 2) fail('CSV has no data rows.');

const header = rows[0].map(h => h.trim().toLowerCase());
const dataRows = rows.slice(1);

const missingRequired = REQUIRED_COLUMNS.filter(c => !header.includes(c));
if (missingRequired.length) fail(`CSV is missing required column(s): ${missingRequired.join(', ')}`);

const unknownColumns = header.filter(h => h && !KNOWN_COLUMNS.includes(h));
if (unknownColumns.length) console.error(`Warning: ignoring unrecognized column(s): ${unknownColumns.join(', ')}`);

const col = (rowObj, name) => (rowObj[name] || '').trim();
const dryRun = !!args['dry-run'];

// Build the existing-journal fingerprint set once, up front, so duplicates
// against already-imported history are caught (not just duplicates within this CSV).
const existingFingerprints = new Set(
  loadAllJournalsTolerant().map(j => contentFingerprint(j))
);

let created = 0, skippedDuplicates = 0, skippedErrors = 0;

dataRows.forEach((cells, idx) => {
  const rowNum = idx + 2; // +1 for header, +1 for 1-indexing
  if (cells.length !== header.length) {
    console.error(`Row ${rowNum}: skipped — expected ${header.length} column(s), got ${cells.length}`);
    skippedErrors++;
    return;
  }
  const rowObj = {};
  header.forEach((h, i) => { rowObj[h] = cells[i] || ''; });

  const title = col(rowObj, 'title');
  if (!title) { console.error(`Row ${rowNum}: skipped, no title`); skippedErrors++; return; }

  const fields = {
    title,
    category: col(rowObj, 'category'),
    severity: col(rowObj, 'severity'),
    status: col(rowObj, 'status'),
    test_name: col(rowObj, 'test_name'),
    seed: col(rowObj, 'seed'),
    failure_signature: col(rowObj, 'failure_signature'),
    symptom: col(rowObj, 'symptom')
  };

  const fp = contentFingerprint(fields);
  if (existingFingerprints.has(fp)) {
    console.error(`Row ${rowNum}: skipped — looks like a duplicate of an already-imported/existing journal ("${title}")`);
    skippedDuplicates++;
    return;
  }

  const tags = col(rowObj, 'tags') ? col(rowObj, 'tags').split(';').map(t => t.trim()).filter(Boolean) : [];
  const fix_files = col(rowObj, 'fix_files')
    ? col(rowObj, 'fix_files').split(';').filter(Boolean).map(spec => {
        const { path, lines } = parseColonSpec(spec);
        return { path, lines, note: '' };
      })
    : [];

  const importFields = {
    ...fields,
    tags,
    owner: col(rowObj, 'owner'),
    hypothesis: col(rowObj, 'hypothesis'),
    root_cause: col(rowObj, 'root_cause'),
    regression_of: col(rowObj, 'regression_of') || null,
    fix_description: col(rowObj, 'fix_description'),
    fix_commit: col(rowObj, 'fix_commit'),
    fix_files,
    resolution: col(rowObj, 'resolution'),
    date_opened: col(rowObj, 'date_opened') || undefined,
    date_predicted: col(rowObj, 'date_predicted') || undefined,
    date_confirmed: col(rowObj, 'date_confirmed') || undefined,
    date_closed: col(rowObj, 'date_closed') || undefined
  };

  if (dryRun) {
    console.log(`[dry-run] would create: ${title} (${fields.category || 'rtl'}/${fields.status || 'investigating'})`);
    existingFingerprints.add(fp); // still dedupe against other rows in the same dry-run
    created++;
    return;
  }

  try {
    const journal = importJournal(importFields);
    console.log(`Created: ${journal.id}`);
    existingFingerprints.add(fp);
    created++;
  } catch (e) {
    console.error(`Row ${rowNum}: skipped — ${e.message}`);
    skippedErrors++;
  }
});

console.log(`\n${dryRun ? 'Would import' : 'Imported'} ${created} journal(s), skipped ${skippedDuplicates} duplicate(s) and ${skippedErrors} error(s) from ${args.file}`);
