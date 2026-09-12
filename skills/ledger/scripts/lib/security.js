'use strict';
const path = require('path');

const SECRET_PATTERNS = [
  ['PRIVATE_KEY', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g],
  ['OPENAI_KEY', /\bsk-[A-Za-z0-9_-]{20,}\b/g],
  ['GITHUB_TOKEN', /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g],
  ['AWS_ACCESS_KEY', /\bAKIA[0-9A-Z]{16}\b/g],
  ['BEARER_TOKEN', /\bBearer\s+[A-Za-z0-9._~+\/-]{20,}=*\b/gi],
  ['PASSWORD', /\b(password|passwd|pwd)\s*[:=]\s*([^\s'";,]+)/gi],
  ['GENERIC_SECRET', /\b(api[_-]?key|secret|token)\s*[:=]\s*['"]?([A-Za-z0-9._~+\/-]{12,})['"]?/gi],
];

function redactSecrets(value) {
  if (value == null) return { text: value, redactions: [] };
  let text = String(value); const redactions = [];
  for (const [name, re] of SECRET_PATTERNS) {
    re.lastIndex = 0;
    if (re.test(text)) redactions.push(name);
    re.lastIndex = 0;
    text = text.replace(re, (...args) => {
      if (name === 'PASSWORD' || name === 'GENERIC_SECRET') return `${args[1]}=[REDACTED_${name}]`;
      return `[REDACTED_${name}]`;
    });
  }
  return { text, redactions: [...new Set(redactions)] };
}

function isSensitivePath(p) {
  if (!p) return false;
  const b = path.basename(String(p)).toLowerCase();
  return b === '.env' || b.includes('credential') || b.includes('secret') || /(?:^|\.)pem$/.test(b) || /(?:^|\.)key$/.test(b);
}

function defaultPolicy() {
  return {
    version: 1,
    redactSecrets: true,
    redactSensitivePathDetails: true,
    checkpointRiskAtOrAbove: 4,
    maxRiskWithoutCheckpoint: 5,
    destructiveCommands: ['rm -rf', 'git reset --hard', 'del /s', 'rmdir /s', 'format ', 'mkfs', 'dd if='],
    sensitivePaths: ['.env', 'credentials', 'secrets', '.ssh'],
    retention: { maxSessions: 500, archiveEndedAfterDays: 30 }
  };
}

function commandRisk(command='') {
  const c = String(command).toLowerCase();
  if (/\b(rm\s+-rf|rmdir\s+\/s|del\s+\/s|format\s+|mkfs|dd\s+if=|shutdown|reboot)\b/.test(c)) return { score: 5, reason: 'destructive shell command' };
  if (/\b(rm|del|rmdir|mv|move|chmod|chown|kill|taskkill)\b/.test(c)) return { score: 4, reason: 'filesystem/process mutation' };
  if (/\b(sed\s+-i|perl\s+-pi|python\s+.*(?:write|unlink|remove)|truncate)\b/.test(c)) return { score: 4, reason: 'bulk/in-place modification' };
  if (/\b(make|ninja|pytest|npm\s+test|cargo\s+test|vcs|xrun|vsim|questa|trs\s+rt)\b/.test(c)) return { score: 2, reason: 'build/test execution' };
  return { score: c ? 1 : 0, reason: c ? 'shell execution' : 'none' };
}

function eventRisk(event) {
  if (event.op === 'delete') return { score: 5, reason: 'delete operation' };
  if (event.op === 'rename') return { score: 3, reason: 'rename/move operation' };
  if (event.op === 'edit') return { score: isSensitivePath(event.path) ? 5 : 2, reason: isSensitivePath(event.path) ? 'edit to sensitive path' : 'file modification' };
  if (event.op === 'create') return { score: isSensitivePath(event.path) ? 4 : 1, reason: isSensitivePath(event.path) ? 'create sensitive file' : 'file creation' };
  if (event.op === 'bash') return commandRisk(event.summary || event.detail || '');
  return { score: 0, reason: 'read-only/other' };
}

module.exports = { redactSecrets, isSensitivePath, defaultPolicy, eventRisk, commandRisk };
