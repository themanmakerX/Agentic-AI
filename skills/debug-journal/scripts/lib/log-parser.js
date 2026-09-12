/**
 * Streams a (possibly multi-GB, possibly gzipped) simulation log line by
 * line instead of loading it into memory, and recognizes more failure
 * patterns than just UVM_ERROR/UVM_FATAL.
 */
const fs = require('fs');
const zlib = require('zlib');
const readline = require('readline');
const { normalizeSignature } = require('./signature');

const FAILURE_PATTERNS = [
  /UVM_ERROR/,
  /UVM_FATAL/,
  /\$fatal\b/i,
  /\bTEST_FAILED\b/i,
  /ASSERTION\s+(?:FAILED|FAILURE)/i,
  /\bFAILED\b.*\bassert/i,
  /^Error:/i,
  /^Error-/i,                         // VCS Error-[CODE]
  /\bFatal:/i,
  /\*E,/,                           // Xcelium
  /segmentation fault/i,
  /simulation.*(?:timeout|timed out)/i,
  /(?:compile|compilation|elaboration).*(?:error|failed|failure)/i,
  /license.*(?:error|fail|denied|unavailable)/i,
  /(?:vcs|xrun|questa|vsim).*(?:fatal|error)/i
];

function findFailures(logPath) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(logPath)) {
      return reject(new Error(`Log file not found: ${logPath}`));
    }
    let stat;
    try {
      stat = fs.statSync(logPath);
    } catch (e) {
      return reject(new Error(`Cannot stat "${logPath}": ${e.message}`));
    }
    if (stat.isDirectory()) {
      return reject(new Error(`Expected a log file but got a directory: ${logPath}`));
    }

    const fileStream = fs.createReadStream(logPath);
    fileStream.on('error', (e) => {
      const reason = e.code === 'EACCES' ? 'permission denied' : (e.code || e.message);
      reject(new Error(`Cannot read "${logPath}": ${reason}`));
    });

    const isGz = logPath.toLowerCase().endsWith('.gz');
    const input = isGz ? fileStream.pipe(zlib.createGunzip()) : fileStream;
    input.on('error', (e) => reject(new Error(`Cannot decompress "${logPath}": ${e.message} (is it really a .gz file?)`)));

    const rl = readline.createInterface({ input, crlfDelay: Infinity });
    const seen = new Set();
    let first = null;
    let totalMatches = 0;
    let binaryWarned = false;

    rl.on('line', (line) => {
      if (!binaryWarned && /[\x00-\x08\x0E-\x1F]/.test(line)) {
        binaryWarned = true; // heuristic: NUL/control bytes suggest a non-text file
      }
      if (FAILURE_PATTERNS.some(re => re.test(line))) {
        totalMatches++;
        const key = normalizeSignature(line) || line.replace(/\s+/g, ' ').trim();
        if (!seen.has(key)) {
          seen.add(key);
          if (!first) first = line.trim();
        }
      }
    });

    rl.on('close', () => {
      resolve({
        firstFailure: first,
        uniqueFailureCount: seen.size,
        totalMatches,
        duplicatesSkipped: totalMatches - seen.size,
        possiblyBinary: binaryWarned
      });
    });
    rl.on('error', (e) => reject(new Error(`Error reading "${logPath}": ${e.message}`)));
  });
}

module.exports = { findFailures, FAILURE_PATTERNS };
