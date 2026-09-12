#!/usr/bin/env node
/**
 * Create a new debug journal entry.
 *
 * Usage:
 *   node create.js --title "AXI write hang under back-to-back bursts" \
 *     --category rtl --severity blocker \
 *     --test-name tb_axi_wr --seed 84213 \
 *     --failure-signature "UVM_ERROR: timeout waiting for BVALID" \
 *     --symptom "Write channel hangs after 3rd back-to-back burst" \
 *     --tags axi,hang,fsm \
 *     --regression-of 2026-08-01_axi-hang-old
 *
 * Optional structured evidence (repeatable):
 *   --evidence-log "sim.log|1042|first UVM_ERROR"
 *   --evidence-waveform "wave.fsdb|1230ns|BVALID never asserts"
 *   --evidence-note "Reproduces on 1/20 seeds"
 *
 * --from-log <path>: streams the log (gzip-aware) looking for the first
 * recognized failure line, and pre-fills --failure-signature/--symptom if
 * not given explicitly.
 *
 * --date-opened YYYY-MM-DD: for backdating (e.g. bulk-logging a bug found
 * yesterday). Defaults to today.
 *
 * TIP: run `node search.js --suggest ...` with the same symptom/tags/file
 * BEFORE creating, to check whether this is a repeat or regression.
 */
const { createJournal } = require('./lib/journal-service');
const { findFailures } = require('./lib/log-parser');
const { parseArgs, toArray, fail } = require('./lib/utils');

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!args.title) fail('--title is required');

  let failureSignature = args['failure-signature'] || '';
  let symptom = args.symptom || '';

  if (args['from-log']) {
    try {
      const result = await findFailures(args['from-log']);
      if (result.possiblyBinary) console.error('Warning: log looks like it may be binary/non-text — results may be unreliable');
      if (result.firstFailure) {
        if (!failureSignature) failureSignature = result.firstFailure.slice(0, 200);
        if (!symptom) symptom = `Auto-captured from log: ${result.firstFailure.slice(0, 200)}`;
        if (result.duplicatesSkipped > 0) console.error(`(deduped ${result.duplicatesSkipped} repeated failure line(s) in the log; ${result.uniqueFailureCount} unique)`);
      } else {
        console.error(`Warning: --from-log "${args['from-log']}" found no recognized failure pattern`);
      }
    } catch (e) {
      fail(e.message);
    }
  }

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

  try {
    const journal = createJournal({
      title: args.title,
      category: args.category,
      severity: args.severity,
      test_name: args['test-name'],
      seed: args.seed,
      failure_signature: failureSignature,
      symptom,
      evidence,
      owner: args.owner,
      regression_of: args['regression-of'] || null,
      related_bugs: toArray(args['related-bug']),
      tags: args.tags ? String(args.tags).split(',').map(t => t.trim()).filter(Boolean) : [],
      date_opened: args['date-opened']
    });

    console.log(`Created journal: ${journal.id}`);
    console.log(`  journals/${journal.id}.json`);
    console.log(`  journals/${journal.id}.md`);
    if (journal.regression_of) console.log(`  Marked as regression of: ${journal.regression_of}`);
  } catch (e) {
    fail(e.message);
  }
}

main();
