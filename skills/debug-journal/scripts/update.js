#!/usr/bin/env node
/**
 * Update an existing debug journal — move status forward through the FSM,
 * add hypothesis, confirm root cause, record structured evidence, and
 * record the fix (files + line numbers) so future bugs can be matched.
 *
 * Usage:
 *   node update.js --id <id> --status predicted --hypothesis "..."
 *
 *   node update.js --id <id> --status confirmed \
 *     --root-cause "..." --fix-description "..." \
 *     --fix-file "rtl/axi_wr_fsm.sv|142-158|added deassert" \
 *     --fix-commit a1b2c3d --owner atif
 *
 * Status values: investigating | predicted | confirmed | retracted
 * Moving OUT of confirmed/retracted requires --reopen (audit-logged).
 * Closing a journal that isn't confirmed/retracted requires --resolution.
 *
 * Structured evidence / fix files are repeatable flags, same format as create.js.
 */
const { updateJournal } = require('./lib/journal-service');
const { parseArgs, toArray, fail } = require('./lib/utils');

const args = parseArgs(process.argv.slice(2));
if (!args.id) fail('--id is required');

const evidence = [];
toArray(args['evidence-log']).forEach(spec => {
  const [file, line, note] = String(spec).split('|').map(s => (s || '').trim());
  evidence.push({ type: 'log', file, line, note });
});
toArray(args['evidence-waveform']).forEach(spec => {
  const [wpath, timestamp, note] = String(spec).split('|').map(s => (s || '').trim());
  evidence.push({ type: 'waveform', path: wpath, timestamp, note });
});
toArray(args['evidence-note']).forEach(text => evidence.push({ type: 'note', text }));

const fix_files = toArray(args['fix-file']).map(spec => {
  const [filePath, lines, note] = String(spec).split('|').map(s => (s || '').trim());
  return { path: filePath, lines, note };
});

try {
  const journal = updateJournal(args.id, {
    status: args.status,
    reopen: !!args.reopen,
    close: !!args.close,
    resolution: args.resolution,
    severity: args.severity,
    hypothesis: args.hypothesis,
    root_cause: args['root-cause'],
    symptom: args.symptom,
    owner: args.owner,
    test_name: args['test-name'],
    seed: args.seed,
    failure_signature: args['failure-signature'],
    regression_of: args['regression-of'],
    related_bugs: toArray(args['related-bug']),
    tags: args.tags ? String(args.tags).split(',').map(t => t.trim()).filter(Boolean) : [],
    evidence,
    fix_description: args['fix-description'],
    fix_commit: args['fix-commit'],
    fix_applied_date: args['fix-applied-date'],
    fix_files
  });
  console.log(`Updated journal: ${journal.id} (status: ${journal.status})`);
} catch (e) {
  fail(e.message);
}
