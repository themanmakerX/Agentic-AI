#!/usr/bin/env node
/**
 * Rebuilds index.json from journals/*.json — the recovery path when the
 * index is corrupted, out of sync, or missing entirely. Also self-invoked
 * automatically by any command that detects a corrupted index.json.
 *
 * Usage:
 *   node rebuild-index.js
 */
const { rebuildIndex } = require('./lib/index-service');

const index = rebuildIndex();
console.log(`Rebuilt index.json from ${index.length} journal(s).`);
