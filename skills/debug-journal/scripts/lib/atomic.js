/**
 * Atomic writes: write to a temp file in the same directory, then rename.
 * rename() is atomic on POSIX and NTFS within the same volume, so a crash
 * mid-write never leaves a half-written journal or index file — readers
 * either see the old complete file or the new complete file, never a mix.
 */
const fs = require('fs');
const path = require('path');

function atomicWriteFile(filePath, content) {
  const dir = path.dirname(filePath);
  const tmp = path.join(dir, `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`);
  fs.writeFileSync(tmp, content);
  fs.renameSync(tmp, filePath);
}

module.exports = { atomicWriteFile };
