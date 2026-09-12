#!/usr/bin/env node
/**
 * Search debug journals — the "have we seen this before" tool.
 *
 * EXACT FILTER MODE (combine with AND):
 *   node search.js --category rtl
 *   node search.js --status predicted
 *   node search.js --tag axi
 *   node search.js --file rtl/axi_wr_fsm.sv
 *   node search.js --file rtl/axi_wr_fsm.sv --lines 150-160
 *   node search.js --text "back-to-back burst"
 *   node search.js --test tb_axi_wr --seed 84213
 *   node search.js --regression
 *
 * SUGGEST MODE (ranked relevance — run before creating a new journal):
 *   node search.js --suggest --symptom "..." --tags axi,hang \
 *     --file rtl/axi_wr_fsm.sv --lines 145-150 \
 *     --failure-signature "UVM_ERROR: timeout waiting for BVALID @ 1230ns"
 */
const { loadIndex } = require('./lib/index-service');
const { loadJournal } = require('./lib/journal-store');
const { rankSimilar } = require('./lib/similarity');
const { parseLines, linesOverlap } = require('./lib/lines');
const { pathsLikelySame, normalizePath } = require('./lib/paths');
const { parseArgs, fail } = require('./lib/utils');

const args = parseArgs(process.argv.slice(2));
const index = loadIndex();

// --lines only makes sense paired with --file — silently ignoring it would
// let a user believe filtering happened when it didn't.
if (args.lines && !args.file) {
  fail('--lines requires --file (line ranges are meaningless without a file to anchor them)');
}

if (args.suggest) {
  const scored = rankSimilar(index, {
    symptom: args.symptom,
    title: args.title,
    tags: args.tags ? String(args.tags).split(',').map(t => t.trim()).filter(Boolean) : [],
    category: args.category,
    file: args.file,
    lines: args.lines,
    failureSignature: args['failure-signature']
  }).slice(0, 10);

  if (scored.length === 0) {
    console.log('No similar past journals found — looks like a new one.');
    process.exit(0);
  }
  console.log(`Top ${scored.length} similar journal(s):\n`);
  scored.forEach(r => {
    console.log(`[score ${r.score}] [${r.entry.status}] ${r.entry.id}`);
    console.log(`  ${r.entry.title}`);
    console.log(`  why: ${r.reasons.join(' | ')}`);
    console.log('');
  });
  process.exit(0);
}

function matches(entry) {
  if (args.category && entry.category !== args.category) return false;
  if (args.status && entry.status !== args.status) return false;
  if (args.workflow && entry.workflow_state !== String(args.workflow).toUpperCase()) return false;
  if (args.severity && entry.severity !== args.severity) return false;
  if (args.test && entry.test_name !== args.test) return false;
  if (args.seed && String(entry.seed) !== String(args.seed)) return false;
  if (args.tag && !entry.tags.includes(String(args.tag).toLowerCase())) return false;
  if (args.regression && !entry.regression_of) return false;
  if (args.file) {
    const queryFile = normalizePath(args.file);
    const queryLines = parseLines(args.lines);
    const fileHit = entry.fix_files.some(f => {
      if (!pathsLikelySame(f.path, queryFile)) return false;
      if (!queryLines) return true;
      const fLines = parseLines(f.lines);
      return fLines ? linesOverlap(queryLines, fLines) : true;
    });
    if (!fileHit) return false;
  }
  return true;
}

let results = index.filter(matches);

if (args.text) {
  const needle = String(args.text).toLowerCase();
  results = results.filter(entry => {
    if (entry.title.toLowerCase().includes(needle) || entry.symptom.toLowerCase().includes(needle)) return true;
    try {
      const full = loadJournal(entry.id);
      const haystack = [full.hypothesis, full.root_cause, full.fix && full.fix.description]
        .filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(needle);
    } catch {
      return false;
    }
  });
}

if (results.length === 0) {
  console.log('No matching journals found.');
  process.exit(0);
}

console.log(`Found ${results.length} matching journal(s):\n`);
results
  .sort((a, b) => (b.date_opened || '').localeCompare(a.date_opened || ''))
  .forEach(e => {
    console.log(`[${e.status}] ${e.id}`);
    console.log(`  ${e.title}`);
    console.log(`  category: ${e.category}  severity: ${e.severity || 'n/a'}  workflow: ${e.workflow_state || 'n/a'}  opened: ${e.date_opened}${e.date_closed ? '  closed: ' + e.date_closed : ''}`);
    if (e.tags.length) console.log(`  tags: ${e.tags.join(', ')}`);
    if (e.fix_files.length) console.log(`  fix touched: ${e.fix_files.map(f => f.path + (f.lines ? ':' + f.lines : '')).join(', ')}`);
    if (e.regression_of) console.log(`  regression of: ${e.regression_of}`);
    console.log('');
  });
