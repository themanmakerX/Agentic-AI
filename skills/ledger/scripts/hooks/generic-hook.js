#!/usr/bin/env node
'use strict';
const L = require('../lib/ledger');
function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', c => { data += c; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}
function fail(msg) { console.error(`generic-hook: ${msg}`); process.exitCode = 1; }
(async () => {
  try {
    const raw = await readStdin();
    const e = JSON.parse(raw || '{}');
    if (!e.session_id) return fail('session_id is required');
    if (!e.op || !L.OPS.has(e.op)) return fail(`op must be one of: ${[...L.OPS].join(', ')}`);
    if (!e.tool) return fail('tool is required');
    if (e.op !== 'bash' && !e.path) return fail('path is required for non-bash events');
    if (e.lines != null) L.normalizeLines(e.lines);
    L.ensureSession(e.session_id, { client: e.client || 'unknown', project: e.project, cwd: e.cwd });
    L.logEvent(e.session_id, { op: e.op, tool: e.tool, path: e.path || e.cwd || null, fromPath: e.from_path || e.fromPath || null, lines: e.lines || null, summary: e.summary || '', detail: e.detail || null, beforeHash: e.before_hash || e.beforeHash || null, afterHash: e.after_hash || e.afterHash || null });
  } catch (err) { fail(err.message); }
})();
