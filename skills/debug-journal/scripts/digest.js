#!/usr/bin/env node
/**
 * Digest of journal activity over a recent window.
 *
 * Usage:
 *   node digest.js                # last 7 days
 *   node digest.js --days 14
 *   node digest.js --days 7 --write   # also saves digest-<date>.md
 */
const fs = require('fs');
const path = require('path');
const { loadAllJournalsTolerant, ROOT } = require('./lib/journal-store');
const { todayISO, parseArgs, fail } = require('./lib/utils');

const args = parseArgs(process.argv.slice(2));

let days = 7;
if (args.days !== undefined) {
  const n = parseInt(args.days, 10);
  if (!Number.isFinite(n) || n <= 0 || String(args.days).trim() !== String(n)) {
    fail(`--days must be a positive integer (got "${args.days}")`);
  }
  days = n;
}

const cutoff = new Date();
cutoff.setDate(cutoff.getDate() - days);
const cutoffStr = cutoff.toISOString().slice(0, 10);

const journals = loadAllJournalsTolerant();

const opened = journals.filter(j => j.date_opened >= cutoffStr);
const confirmed = journals.filter(j => j.date_confirmed && j.date_confirmed >= cutoffStr);
const stillOpen = journals.filter(j => j.workflow_state === 'OPEN');

const lines = [];
lines.push(`# Debug Journal Digest — last ${days} day(s)`);
lines.push(`Generated: ${todayISO()}`);
lines.push('');
lines.push(`## Opened (${opened.length})`);
if (!opened.length) lines.push('_none_');
opened.forEach(j => lines.push(`- [${j.severity}] ${j.id} — ${j.title} (${j.category}, ${j.status})`));
lines.push('');
lines.push(`## Confirmed / fixed (${confirmed.length})`);
if (!confirmed.length) lines.push('_none_');
confirmed.forEach(j => {
  const fixSummary = j.fix && j.fix.files && j.fix.files.length ? j.fix.files.map(f => f.path).join(', ') : 'no files recorded';
  lines.push(`- ${j.id} — ${j.title} (fix: ${fixSummary})`);
});
lines.push('');
lines.push(`## Still open (${stillOpen.length})`);
if (!stillOpen.length) lines.push('_none_');
stillOpen.sort((a, b) => a.date_opened.localeCompare(b.date_opened))
  .forEach(j => lines.push(`- [${j.status}] ${j.id} — ${j.title} (opened ${j.date_opened})`));
lines.push('');

const out = lines.join('\n');
console.log(out);

if (args.write) {
  const outPath = path.join(ROOT, `digest-${todayISO()}.md`);
  fs.writeFileSync(outPath, out);
  console.error(`\nSaved to ${outPath}`);
}
