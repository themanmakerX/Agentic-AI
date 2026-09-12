/**
 * Diagnosis status and workflow closure are orthogonal in schema v3.
 * status describes what we know; workflow_state describes whether work is open.
 */
const FORWARD_TRANSITIONS = {
  investigating: ['predicted', 'confirmed', 'retracted'],
  predicted: ['investigating', 'confirmed', 'retracted'],
  confirmed: [],
  retracted: []
};

const CLOSED_DIAGNOSIS_STATES = ['confirmed', 'retracted'];

function canTransition(from, to, { reopen = false, workflowState = 'OPEN' } = {}) {
  if (workflowState === 'CLOSED') {
    if (!reopen) {
      return { ok: false, reason: `journal workflow is CLOSED — moving diagnosis from "${from}" to "${to}" requires --reopen` };
    }
    if (CLOSED_DIAGNOSIS_STATES.includes(to)) {
      return { ok: false, reason: `--reopen must move to an open diagnosis (investigating/predicted), not "${to}"` };
    }
    return { ok: true, reopened: true };
  }

  if (from === to) return { ok: true, note: 'no-op (status unchanged)' };
  if (CLOSED_DIAGNOSIS_STATES.includes(from)) {
    // v2 journals may be inconsistent (closed diagnosis but workflow inferred OPEN).
    if (!reopen) return { ok: false, reason: `"${from}" is a closed diagnosis — moving to "${to}" requires --reopen` };
    if (CLOSED_DIAGNOSIS_STATES.includes(to)) return { ok: false, reason: `--reopen must move to investigating/predicted, not "${to}"` };
    return { ok: true, reopened: true };
  }
  if (!FORWARD_TRANSITIONS[from] || !FORWARD_TRANSITIONS[from].includes(to)) {
    return { ok: false, reason: `"${from}" -> "${to}" is not a valid transition (allowed: ${(FORWARD_TRANSITIONS[from] || []).join(', ') || 'none'})` };
  }
  return { ok: true };
}

module.exports = { canTransition, CLOSED_DIAGNOSIS_STATES, FORWARD_TRANSITIONS };
