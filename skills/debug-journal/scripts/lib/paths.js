/**
 * Path normalization — used everywhere a file path is stored or compared,
 * so "rtl\axi.sv", "./rtl/axi.sv", and "rtl/axi.sv" are recognized as the
 * same file instead of three different strings.
 */
const path = require('path');

function normalizePath(p) {
  if (!p) return '';
  let s = String(p).trim();
  s = s.replace(/\\/g, '/');           // Windows separators -> posix
  s = s.replace(/^\.\//, '');           // leading ./
  s = s.replace(/\/+/g, '/');           // collapse //
  // Collapse ../ and ./ segments where possible without touching a drive letter prefix
  const driveMatch = s.match(/^([a-zA-Z]:)(\/.*)$/);
  if (driveMatch) {
    return driveMatch[1] + path.posix.normalize(driveMatch[2]);
  }
  return path.posix.normalize(s);
}

function pathsEqual(a, b) {
  return normalizePath(a) === normalizePath(b);
}

function basename(p) {
  return normalizePath(p).split('/').pop();
}

// True only for a normalized-path match or a same-basename + shared parent
// directory segment — plain substring matching (e.g. "fsm.sv" matching any
// file ending in those characters) is deliberately excluded to avoid false
// positives in similarity scoring.
function pathsLikelySame(a, b) {
  const na = normalizePath(a), nb = normalizePath(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  // Permit absolute-vs-repo-relative equivalence only when the shorter path
  // contains directory context. A bare "fsm.sv" is too ambiguous to match
  // every file with that basename.
  const aParts = na.split('/'), bParts = nb.split('/');
  if (aParts.length < 2 || bParts.length < 2) return false;
  return na.endsWith('/' + nb) || nb.endsWith('/' + na);
}

// Parses a "path:lines" spec (used by CSV import) without being fooled by a
// Windows drive letter colon, e.g. "C:\repo\foo.sv:10-20" -> path="C:\repo\foo.sv", lines="10-20"
function parseColonSpec(spec) {
  const s = String(spec).trim();
  const m = s.match(/^(.*):(\d+(?:-\d+)?)$/);
  if (m) return { path: m[1].trim(), lines: m[2].trim() };
  return { path: s, lines: '' };
}

module.exports = { normalizePath, pathsEqual, basename, pathsLikelySame, parseColonSpec };
