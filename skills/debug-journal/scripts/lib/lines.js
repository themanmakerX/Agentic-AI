// Non-throwing line-range helpers for search/similarity (schema.js has the
// throwing validator used at write time; this is the read-time counterpart).
function parseLines(spec) {
  if (!spec) return null;
  const s = String(spec).trim();
  if (!s) return null;
  const range = s.match(/^(\d+)\s*-\s*(\d+)$/);
  if (range) return [parseInt(range[1], 10), parseInt(range[2], 10)];
  const single = s.match(/^(\d+)$/);
  if (single) return [parseInt(single[1], 10), parseInt(single[1], 10)];
  return null;
}

function linesOverlap(a, b) {
  if (!a || !b) return false;
  return a[0] <= b[1] && b[0] <= a[1];
}

module.exports = { parseLines, linesOverlap };
