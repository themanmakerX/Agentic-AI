/**
 * Best-effort normalization of DV failure signatures so that runs differing
 * only in dynamic values (timestamps, addresses, seeds) still match. This is
 * heuristic, not a full UVM log grammar — see SKILL.md "known limitations".
 */
function normalizeSignature(sig) {
  if (!sig) return '';
  let s = String(sig).toLowerCase();
  s = s.replace(/0x[0-9a-f]+/g, '<hex>');
  s = s.replace(/@\s*\d+\s*(ns|ps|us|fs)\b/g, '<time>');
  s = s.replace(/\btime\s*[:=]\s*\d+/g, 'time=<n>');
  s = s.replace(/\bseed\s*[:=]\s*\d+/g, 'seed=<n>');
  s = s.replace(/\b\d+\b/g, '#'); // remaining bare numbers (line nos, counts, etc.)
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

// Heuristic extraction of a UVM component hierarchy path, e.g.
// "uvm_test_top.env.agent.driver" — used as an extra similarity signal.
function extractComponentPath(sig) {
  if (!sig) return '';
  const m = String(sig).match(/\b((?:uvm_test_top|tb_top)(?:\.[a-zA-Z_]\w*)+)\b/);
  return m ? m[1] : '';
}

// Heuristic extraction of an assertion/property name (all-caps token, 4+ chars).
function extractAssertionId(sig) {
  if (!sig) return '';
  const m = String(sig).match(/\b([A-Z][A-Z0-9_]{3,})\b/);
  return m ? m[1] : '';
}

module.exports = { normalizeSignature, extractComponentPath, extractAssertionId };
