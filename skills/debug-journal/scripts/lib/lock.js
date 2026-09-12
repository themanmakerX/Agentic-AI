/**
 * Exclusive single-machine lock with ownership tokens.
 *
 * Important properties:
 * - A live process is never evicted just because it ran for >10 seconds.
 * - Dead-owner locks are reclaimed safely via atomic rename.
 * - releaseLock() only removes a lock if the caller still owns its token.
 * - Malformed legacy locks are reclaimed only after a conservative timeout.
 */
const fs = require('fs');
const crypto = require('crypto');

const MALFORMED_STALE_MS = 5 * 60 * 1000;
const DEFAULT_TIMEOUT_MS = 15000;
const RETRY_MS = 25;

function sleepSync(ms) {
  const sab = new SharedArrayBuffer(4);
  Atomics.wait(new Int32Array(sab), 0, 0, ms);
}

function pidIsAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === 'EPERM'; // exists but not signalable by this user
  }
}

function readLock(lockPath) {
  try {
    const raw = fs.readFileSync(lockPath, 'utf8').trim();
    try {
      const obj = JSON.parse(raw);
      if (obj && Number.isInteger(obj.pid) && typeof obj.token === 'string' && obj.token) return obj;
    } catch { /* legacy/plain PID lock handled below */ }
    if (/^\d+$/.test(raw)) return { pid: Number(raw), token: null, legacy: true };
    return { malformed: true };
  } catch (e) {
    if (e.code === 'ENOENT') return null;
    throw e;
  }
}

function reclaimLock(lockPath) {
  const quarantine = `${lockPath}.stale.${process.pid}.${Date.now()}.${crypto.randomBytes(3).toString('hex')}`;
  try {
    fs.renameSync(lockPath, quarantine); // atomic winner among competing reclaimers
    try { fs.unlinkSync(quarantine); } catch { /* harmless */ }
    return true;
  } catch (e) {
    if (e.code === 'ENOENT' || e.code === 'EACCES' || e.code === 'EPERM') return false;
    return false;
  }
}

function acquireLock(lockPath, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const start = Date.now();
  const token = crypto.randomBytes(16).toString('hex');
  const payload = JSON.stringify({ pid: process.pid, token, created_at: new Date().toISOString() });

  for (;;) {
    try {
      const fd = fs.openSync(lockPath, 'wx');
      try {
        fs.writeFileSync(fd, payload, 'utf8');
        fs.fsyncSync(fd);
      } finally {
        fs.closeSync(fd);
      }
      return token;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;

      let info = null;
      try { info = readLock(lockPath); } catch { /* retry */ }
      let reclaim = false;
      if (info && Number.isInteger(info.pid) && !pidIsAlive(info.pid)) {
        reclaim = true;
      } else if (info && info.malformed) {
        try { reclaim = (Date.now() - fs.statSync(lockPath).mtimeMs) > MALFORMED_STALE_MS; } catch { /* vanished */ }
      }
      if (reclaim && reclaimLock(lockPath)) continue;

      if (Date.now() - start > timeoutMs) {
        const owner = info && info.pid ? ` (owner pid ${info.pid}${pidIsAlive(info.pid) ? ' appears alive' : ' appears dead'})` : '';
        throw new Error(`Could not acquire lock at ${lockPath} within ${timeoutMs}ms${owner}. If no process is running, inspect/remove the lock manually.`);
      }
      sleepSync(RETRY_MS);
    }
  }
}

function releaseLock(lockPath, token) {
  try {
    const info = readLock(lockPath);
    if (!info) return;
    // Never unlink somebody else's replacement lock.
    if (!info.token || info.token !== token) return;
    fs.unlinkSync(lockPath);
  } catch { /* lock already gone or replaced */ }
}

function withLock(lockPath, fn) {
  const token = acquireLock(lockPath);
  try {
    return fn();
  } finally {
    releaseLock(lockPath, token);
  }
}

module.exports = { withLock, acquireLock, releaseLock, pidIsAlive };
