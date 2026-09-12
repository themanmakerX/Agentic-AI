const { pathsLikelySame, normalizePath } = require('./paths');
const { normalizeSignature, extractComponentPath, extractAssertionId } = require('./signature');
const { parseLines, linesOverlap } = require('./lines');

function wordsOf(s) {
  return String(s || '').toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length > 2);
}

/**
 * Scores every entry in the index against a query. Returns entries with
 * score > 0, sorted descending, each with a human-readable `reasons` list.
 *
 * query: { symptom, title, tags[], category, file, lines, failureSignature }
 */
function rankSimilar(index, query) {
  const queryTags = (query.tags || []).map(t => String(t).trim().toLowerCase()).filter(Boolean);
  const queryLines = parseLines(query.lines);
  const queryWords = new Set([...wordsOf(query.symptom), ...wordsOf(query.title)]);
  const querySigNorm = normalizeSignature(query.failureSignature);
  const queryComponent = extractComponentPath(query.failureSignature);
  const queryAssertion = extractAssertionId(query.failureSignature);
  const queryFileNorm = query.file ? normalizePath(query.file) : '';

  const scored = index.map(entry => {
    let score = 0;
    const reasons = [];

    const tagOverlap = queryTags.filter(t => entry.tags.includes(t));
    if (tagOverlap.length) { score += tagOverlap.length * 5; reasons.push(`tags: ${tagOverlap.join(', ')}`); }

    if (query.category && entry.category === query.category) { score += 4; reasons.push('same category'); }

    if (queryFileNorm) {
      entry.fix_files.forEach(f => {
        if (pathsLikelySame(f.path, queryFileNorm)) {
          const fLines = parseLines(f.lines);
          if (queryLines && fLines && linesOverlap(queryLines, fLines)) {
            score += 12; reasons.push(`fix overlaps lines in ${f.path} (${f.lines})`);
          } else {
            score += 6; reasons.push(`past fix touched ${f.path}`);
          }
        }
      });
    }

    if (querySigNorm && entry.failure_signature) {
      const entrySigNorm = normalizeSignature(entry.failure_signature);
      if (entrySigNorm && entrySigNorm === querySigNorm) {
        score += 15; reasons.push('normalized failure signature matches exactly');
      }
    }

    if (queryComponent && entry.failure_signature) {
      const entryComponent = extractComponentPath(entry.failure_signature);
      if (entryComponent && entryComponent === queryComponent) { score += 8; reasons.push(`same component path (${queryComponent})`); }
    }

    if (queryAssertion && entry.failure_signature) {
      const entryAssertion = extractAssertionId(entry.failure_signature);
      if (entryAssertion && entryAssertion === queryAssertion) { score += 8; reasons.push(`same assertion/token (${queryAssertion})`); }
    }

    if (queryWords.size) {
      const entryWords = new Set([...wordsOf(entry.title), ...wordsOf(entry.symptom)]);
      const overlap = [...queryWords].filter(w => entryWords.has(w));
      if (overlap.length) { score += overlap.length * 2; reasons.push(`text overlap: ${overlap.slice(0, 5).join(', ')}`); }
    }

    if (entry.regression_of) { score += 1; reasons.push('has a prior regression link (recurring area)'); }

    return { entry, score, reasons };
  })
  .filter(r => r.score > 0)
  .sort((a, b) => b.score - a.score);

  return scored;
}

module.exports = { rankSimilar };
