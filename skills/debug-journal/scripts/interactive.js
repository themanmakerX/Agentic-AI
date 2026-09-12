#!/usr/bin/env node
/**
 * Interactive mode — prompts for fields instead of remembering all the flags.
 * Runs the same validated createJournal()/updateJournal() path as the flag-based
 * scripts, so everything (id collision safety, FSM, relationship checks) applies here too.
 *
 * Usage:
 *   node interactive.js
 */
const readline = require('readline');
const { createJournal, updateJournal } = require('./lib/journal-service');
const schema = require('./lib/schema');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise(res => rl.question(q, res));

async function main() {
  console.log('New debug journal (press Enter to skip optional fields)\n');

  const title = (await ask('Title: ')).trim();
  if (!title) { console.log('Title is required, aborting.'); rl.close(); return; }

  let category = (await ask(`Category [${schema.CATEGORIES.join('/')}] (default rtl): `)).trim();
  if (!schema.CATEGORIES.includes(category)) category = 'rtl';

  let severity = (await ask(`Severity [${schema.SEVERITIES.join('/')}] (default major): `)).trim();
  if (!schema.SEVERITIES.includes(severity)) severity = 'major';

  const test_name = (await ask('Test name: ')).trim();
  const seed = (await ask('Seed: ')).trim();
  const failure_signature = (await ask('Failure signature (log line/assertion): ')).trim();
  const symptom = (await ask('Symptom (what you observed): ')).trim();
  const tagsRaw = (await ask('Tags (comma-separated): ')).trim();
  const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];
  const owner = (await ask('Owner (blank = unassigned): ')).trim();
  const regression_of = (await ask('Regression of (past journal id, blank if none): ')).trim();

  let journal;
  try {
    journal = createJournal({ title, category, severity, test_name, seed, failure_signature, symptom, owner, tags, regression_of: regression_of || null });
  } catch (e) {
    console.log(`\nCould not create journal: ${e.message}`);
    rl.close();
    return;
  }
  console.log(`\nCreated journal: ${journal.id}`);

  const wantsHypothesis = (await ask('\nDo you already have a hypothesis? (y/N): ')).trim().toLowerCase();
  if (wantsHypothesis === 'y') {
    const hypothesis = (await ask('Hypothesis: ')).trim();
    try {
      journal = updateJournal(journal.id, { status: 'predicted', hypothesis });
      console.log('Status set to "predicted".');
    } catch (e) {
      console.log(`Could not update: ${e.message}`);
    }
  }

  console.log(`\nDone. Use update.js --id ${journal.id} ... to confirm root cause and record the fix later.`);
  rl.close();
}

main();
