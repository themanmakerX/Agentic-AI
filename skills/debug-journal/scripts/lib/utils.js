const crypto = require('crypto');

function slugify(str) {
  const s = String(str)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 60);
  return s || `bug-${crypto.randomBytes(3).toString('hex')}`;
}

// Use the machine's local calendar date, not UTC. Debug journals are normally
// created on a developer workstation and should follow that workstation's day.
function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// Strict Gregorian YYYY-MM-DD validation. JS Date otherwise normalizes values
// such as 2026-02-31 into March, which must never be accepted as a journal date.
function isValidISODate(s) {
  if (typeof s !== 'string') return false;
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return false;
  const y = Number(m[1]), mon = Number(m[2]), day = Number(m[3]);
  if (mon < 1 || mon > 12 || day < 1) return false;
  const daysInMonth = new Date(Date.UTC(y, mon, 0)).getUTCDate();
  return day <= daysInMonth;
}

function daysBetween(a, b) {
  if (!a || !b || !isValidISODate(a) || !isValidISODate(b)) return null;
  const [ay, am, ad] = a.split('-').map(Number);
  const [by, bm, bd] = b.split('-').map(Number);
  return Math.round((Date.UTC(by, bm - 1, bd) - Date.UTC(ay, am - 1, ad)) / 86400000);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const tok = argv[i];
    if (!tok.startsWith('--')) continue;
    const key = tok.slice(2);
    const val = (i + 1 < argv.length && !argv[i + 1].startsWith('--')) ? argv[++i] : true;
    if (key in args) args[key] = Array.isArray(args[key]) ? [...args[key], val] : [args[key], val];
    else args[key] = val;
  }
  return args;
}

function toArray(v) {
  if (v === undefined) return [];
  return Array.isArray(v) ? v : [v];
}

function fail(msg) {
  console.error(`Error: ${msg}`);
  process.exit(1);
}

module.exports = { slugify, todayISO, isValidISODate, daysBetween, parseArgs, toArray, fail };
