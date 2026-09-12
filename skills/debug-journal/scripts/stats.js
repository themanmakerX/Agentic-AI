#!/usr/bin/env node
/**
 * Rollup stats across all journals — category/status/severity breakdown,
 * average time-to-confirm, most-touched files, and regression count.
 * Corrupted individual journal files are skipped with a warning rather
 * than crashing the whole command.
 *
 * Usage:
 *   node stats.js
 */
const { loadAllJournalsTolerant } = require('./lib/journal-store');
const { daysBetween } = require('./lib/utils');

const journals = loadAllJournalsTolerant();

if (journals.length === 0) {
  console.log('No journals yet.');
  process.exit(0);
}

function tally(items, key) {
  const t = {};
  items.forEach(j => { const v = j[key] || '(unset)'; t[v] = (t[v] || 0) + 1; });
  return t;
}
function printTally(label, t) {
  console.log(label);
  Object.entries(t).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${k}: ${v}`));
  console.log('');
}

console.log(`Total journals: ${journals.length}\n`);
printTally('By category:', tally(journals, 'category'));
printTally('By status:', tally(journals, 'status'));
printTally('By workflow state:', tally(journals, 'workflow_state'));
printTally('By severity:', tally(journals, 'severity'));

const confirmedWithTimes = journals.filter(j => j.date_opened && j.date_confirmed);
if (confirmedWithTimes.length) {
  const times = confirmedWithTimes.map(j => daysBetween(j.date_opened, j.date_confirmed));
  const avg = (times.reduce((a, b) => a + b, 0) / times.length).toFixed(1);
  console.log(`Average time to confirm root cause: ${avg} day(s) (n=${times.length})\n`);
} else {
  console.log('Average time to confirm root cause: no confirmed journals yet\n');
}

const fileCounts = {};
journals.forEach(j => (j.fix && j.fix.files ? j.fix.files : []).forEach(f => {
  fileCounts[f.path] = (fileCounts[f.path] || 0) + 1;
}));
const topFiles = Object.entries(fileCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);
if (topFiles.length) {
  console.log('Most-touched files (candidates for hardening/refactor):');
  topFiles.forEach(([f, c]) => console.log(`  ${f}: ${c} fix(es)`));
  console.log('');
}

const regressions = journals.filter(j => j.regression_of);
console.log(`Regressions logged: ${regressions.length}`);
regressions.forEach(j => console.log(`  ${j.id} (regression of ${j.regression_of})`));

const reopened = journals.filter(j => (j.status_history || []).some(h => h.note === 'reopened'));
if (reopened.length) {
  console.log(`\nJournals reopened at least once: ${reopened.length}`);
  reopened.forEach(j => console.log(`  ${j.id}`));
}
