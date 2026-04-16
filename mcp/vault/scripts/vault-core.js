import crypto from 'crypto';
import fs from 'fs/promises';
import os from 'os';
import path from 'path';

export const DEFAULT_HOME = path.join(os.homedir(), '.vault');
export const GLOBAL_CONFIG_FILE = 'config.json';
export const VAULT_META_DIR = '.vault';

const DEFAULT_STATE = {
  version: 1,
  activeVaultPath: null,
  vaults: [],
};

const DATA_FILES = {
  metadata: 'vault.json',
  records: 'records.jsonl',
  facts: 'facts.jsonl',
  links: 'links.jsonl',
  journal: 'journal.jsonl',
  index: 'index.json',
};

const TOKEN_RE = /[a-z0-9]{2,}/g;

const nowIso = () => new Date().toISOString();

const normalizeText = (value) =>
  String(value ?? '')
    .normalize('NFKD')
    .replace(/[^\x00-\x7F]/g, ' ')
    .toLowerCase();

const tokenize = (value) => {
  const text = normalizeText(value);
  return text.match(TOKEN_RE) ?? [];
};

const safeBasename = (value, fallback) => {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  const cleaned = text.replace(/[<>:"/\\|?*\x00-\x1F]/g, '-').replace(/\s+/g, '-');
  return cleaned.slice(0, 80) || fallback;
};

const ensureDir = async (dir) => {
  await fs.mkdir(dir, { recursive: true });
};

const readJson = async (file, fallback) => {
  try {
    const raw = await fs.readFile(file, 'utf8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
};

const writeJson = async (file, value) => {
  await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
};

const appendJsonl = async (file, value) => {
  await fs.appendFile(file, `${JSON.stringify(value)}\n`, 'utf8');
};

const readJsonl = async (file) => {
  try {
    const raw = await fs.readFile(file, 'utf8');
    return raw
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch {
    return [];
  }
};

const ensureVaultMetadata = async (vaultRoot, name) => {
  const metaDir = path.join(vaultRoot, VAULT_META_DIR);
  await ensureDir(metaDir);
  await Promise.all(
    Object.values(DATA_FILES).map((fileName) => {
      const filePath = path.join(metaDir, fileName);
      return fs.access(filePath).catch(async () => {
        if (fileName.endsWith('.json')) {
          await writeJson(filePath, fileName === DATA_FILES.index ? { rebuiltAt: null } : {});
          return;
        }
        await fs.writeFile(filePath, '', 'utf8');
      });
    }),
  );

  const vaultFile = path.join(metaDir, DATA_FILES.metadata);
  const existing = await readJson(vaultFile, null);
  if (!existing || !existing.id) {
    const createdAt = nowIso();
    const metadata = {
      id: crypto.randomUUID(),
      name: name || path.basename(vaultRoot),
      path: path.resolve(vaultRoot),
      createdAt,
      lastOpenedAt: createdAt,
    };
    await writeJson(vaultFile, metadata);
    return metadata;
  }

  return existing;
};

export const resolveGlobalHome = (homeDir = DEFAULT_HOME) => path.resolve(homeDir);

export const globalConfigPath = (homeDir = DEFAULT_HOME) =>
  path.join(resolveGlobalHome(homeDir), GLOBAL_CONFIG_FILE);

export const defaultVaultPath = () => path.join(os.homedir(), 'Vault');

export const loadState = async (homeDir = DEFAULT_HOME) => {
  const root = resolveGlobalHome(homeDir);
  await ensureDir(root);
  const file = globalConfigPath(root);
  const state = await readJson(file, null);
  if (!state || typeof state !== 'object') {
    await writeJson(file, DEFAULT_STATE);
    return structuredClone(DEFAULT_STATE);
  }
  return {
    ...structuredClone(DEFAULT_STATE),
    ...state,
    vaults: Array.isArray(state.vaults) ? state.vaults : [],
  };
};

export const saveState = async (state, homeDir = DEFAULT_HOME) => {
  const root = resolveGlobalHome(homeDir);
  await ensureDir(root);
  await writeJson(globalConfigPath(root), state);
};

export const listVaults = async (homeDir = DEFAULT_HOME) => {
  const state = await loadState(homeDir);
  return state.vaults
    .map((vault) => ({
      ...vault,
      path: path.resolve(vault.path),
      active: state.activeVaultPath && path.resolve(state.activeVaultPath) === path.resolve(vault.path),
    }))
    .sort((a, b) => String(a.name).localeCompare(String(b.name)));
};

export const registerVault = async ({ vaultPath, name, homeDir = DEFAULT_HOME, activate = true }) => {
  const resolvedVaultPath = path.resolve(vaultPath);
  await ensureDir(resolvedVaultPath);
  const metadata = await ensureVaultMetadata(resolvedVaultPath, name);
  const state = await loadState(homeDir);
  const existingIndex = state.vaults.findIndex(
    (vault) => path.resolve(vault.path) === resolvedVaultPath,
  );
  const entry = {
    id: metadata.id,
    name: metadata.name,
    path: resolvedVaultPath,
    createdAt: metadata.createdAt,
    lastOpenedAt: nowIso(),
  };

  if (existingIndex >= 0) {
    state.vaults[existingIndex] = {
      ...state.vaults[existingIndex],
      ...entry,
    };
  } else {
    state.vaults.push(entry);
  }

  if (activate) {
    state.activeVaultPath = resolvedVaultPath;
  }

  await saveState(state, homeDir);
  await writeJson(path.join(resolvedVaultPath, VAULT_META_DIR, DATA_FILES.metadata), {
    ...metadata,
    name: entry.name,
    path: resolvedVaultPath,
    lastOpenedAt: entry.lastOpenedAt,
  });

  return entry;
};

export const chooseVault = async ({ vaultPath, name, homeDir = DEFAULT_HOME }) =>
  registerVault({ vaultPath, name, homeDir, activate: true });

export const ensureActiveVault = async (homeDir = DEFAULT_HOME) => {
  const state = await loadState(homeDir);
  if (!state.activeVaultPath) {
    return { state, active: null };
  }
  const activePath = path.resolve(state.activeVaultPath);
  const vaults = await listVaults(homeDir);
  const active = vaults.find((vault) => path.resolve(vault.path) === activePath) ?? null;
  return { state, active };
};

export const getVaultFiles = (vaultPath) => {
  const metaDir = path.join(path.resolve(vaultPath), VAULT_META_DIR);
  return {
    metaDir,
    metadata: path.join(metaDir, DATA_FILES.metadata),
    records: path.join(metaDir, DATA_FILES.records),
    facts: path.join(metaDir, DATA_FILES.facts),
    links: path.join(metaDir, DATA_FILES.links),
    journal: path.join(metaDir, DATA_FILES.journal),
    index: path.join(metaDir, DATA_FILES.index),
  };
};

export const ensureVault = async ({ vaultPath, name, homeDir = DEFAULT_HOME }) => {
  const entry = await registerVault({ vaultPath, name, homeDir, activate: true });
  return {
    ...entry,
    files: getVaultFiles(entry.path),
  };
};

export const getActiveVault = async (homeDir = DEFAULT_HOME) => {
  const { active } = await ensureActiveVault(homeDir);
  return active;
};

export const setActiveVault = async ({ vaultPath, homeDir = DEFAULT_HOME }) => {
  const state = await loadState(homeDir);
  const resolved = path.resolve(vaultPath);
  if (!state.vaults.some((vault) => path.resolve(vault.path) === resolved)) {
    throw new Error(`Vault not registered: ${resolved}`);
  }
  state.activeVaultPath = resolved;
  await saveState(state, homeDir);
  return resolved;
};

export const createVault = async ({ vaultPath, name, homeDir = DEFAULT_HOME, activate = true }) => {
  const entry = await registerVault({ vaultPath, name, homeDir, activate });
  return {
    ...entry,
    files: getVaultFiles(entry.path),
  };
};

export const loadActiveVaultFiles = async (homeDir = DEFAULT_HOME) => {
  const active = await getActiveVault(homeDir);
  if (!active) {
    return null;
  }
  return getVaultFiles(active.path);
};

export const loadRecords = async (vaultPath) => {
  const { records } = getVaultFiles(vaultPath);
  return readJsonl(records);
};

export const loadFacts = async (vaultPath) => {
  const { facts } = getVaultFiles(vaultPath);
  return readJsonl(facts);
};

export const loadLinks = async (vaultPath) => {
  const { links } = getVaultFiles(vaultPath);
  return readJsonl(links);
};

export const loadJournal = async (vaultPath) => {
  const { journal } = getVaultFiles(vaultPath);
  return readJsonl(journal);
};

export const addRecord = async ({
  vaultPath,
  title = '',
  content,
  tags = [],
  source = '',
  kind = 'record',
  metadata = {},
}) => {
  const files = getVaultFiles(vaultPath);
  const createdAt = nowIso();
  const record = {
    id: crypto.randomUUID(),
    title: String(title ?? '').trim(),
    content: String(content ?? ''),
    tags: Array.isArray(tags) ? tags.map(String) : [],
    source: String(source ?? '').trim(),
    kind: String(kind ?? 'record'),
    createdAt,
    updatedAt: createdAt,
    metadata,
  };
  await appendJsonl(files.records, record);
  return record;
};

export const addJournalEntry = async ({
  vaultPath,
  sessionId = '',
  entryType = 'checkpoint',
  note = '',
  metadata = {},
}) => {
  const files = getVaultFiles(vaultPath);
  const createdAt = nowIso();
  const entry = {
    id: crypto.randomUUID(),
    sessionId: String(sessionId ?? ''),
    entryType: String(entryType ?? 'checkpoint'),
    note: String(note ?? ''),
    metadata,
    createdAt,
  };
  await appendJsonl(files.journal, entry);
  return entry;
};

export const addFact = async ({
  vaultPath,
  subject,
  predicate,
  object,
  validFrom = null,
  validTo = null,
  confidence = 1,
  sourceRecordId = null,
}) => {
  const files = getVaultFiles(vaultPath);
  const fact = {
    id: crypto.randomUUID(),
    subject: String(subject ?? '').trim(),
    predicate: String(predicate ?? '').trim(),
    object: String(object ?? '').trim(),
    validFrom,
    validTo,
    confidence: Number(confidence ?? 1),
    sourceRecordId,
    createdAt: nowIso(),
  };
  await appendJsonl(files.facts, fact);
  return fact;
};

export const addLink = async ({
  vaultPath,
  fromRecordId,
  toRecordId,
  label = '',
  sourceRecordId = null,
}) => {
  const files = getVaultFiles(vaultPath);
  const link = {
    id: crypto.randomUUID(),
    fromRecordId,
    toRecordId,
    label: String(label ?? ''),
    sourceRecordId,
    createdAt: nowIso(),
  };
  await appendJsonl(files.links, link);
  return link;
};

export const recordSnippet = (record, maxLength = 220) => {
  const text = String(record?.content ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  return text.length > maxLength ? `${text.slice(0, maxLength - 3)}...` : text;
};

const scoreRecord = (queryTokens, record) => {
  const haystack = normalizeText([record.title, record.content, ...(record.tags ?? []), record.source].join(' '));
  let score = 0;
  for (const token of queryTokens) {
    if (haystack.includes(token)) score += 2;
  }
  if (queryTokens.length > 0 && queryTokens.every((token) => haystack.includes(token))) {
    score += 3;
  }
  if (record.title && queryTokens.some((token) => normalizeText(record.title).includes(token))) {
    score += 2;
  }
  if (record.tags?.length) {
    const tagHit = record.tags.map(normalizeText).some((tag) => queryTokens.some((token) => tag.includes(token)));
    if (tagHit) score += 1;
  }
  const ageMs = Date.now() - new Date(record.createdAt).getTime();
  const ageDays = Number.isFinite(ageMs) ? ageMs / (1000 * 60 * 60 * 24) : 0;
  score += Math.max(0, 1 - ageDays / 365);
  return score;
};

export const searchRecords = async ({ vaultPath, query = '', limit = 5, kind = null, tag = null }) => {
  const records = await loadRecords(vaultPath);
  const queryTokens = tokenize(query);
  const filtered = records.filter((record) => {
    if (kind && record.kind !== kind) return false;
    if (tag && !(record.tags ?? []).map(normalizeText).includes(normalizeText(tag))) return false;
    return true;
  });

  const results = filtered
    .map((record) => ({
      ...record,
      score: queryTokens.length ? scoreRecord(queryTokens, record) : 0,
      preview: recordSnippet(record),
    }))
    .sort((a, b) => {
      if (queryTokens.length && b.score !== a.score) return b.score - a.score;
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });

  return results.slice(0, Math.max(1, Number(limit) || 5));
};

export const queryFacts = async ({ vaultPath, subject, asOf = null, direction = 'both' }) => {
  const facts = await loadFacts(vaultPath);
  const needle = normalizeText(subject);
  return facts.filter((fact) => {
    const subjectHit = normalizeText(fact.subject).includes(needle);
    const objectHit = normalizeText(fact.object).includes(needle);
    const matchesDirection =
      direction === 'both' ||
      (direction === 'outgoing' && subjectHit) ||
      (direction === 'incoming' && objectHit);
    if (!matchesDirection) return false;
    if (asOf) {
      const asOfTime = new Date(asOf).getTime();
      const fromOk = !fact.validFrom || new Date(fact.validFrom).getTime() <= asOfTime;
      const toOk = !fact.validTo || new Date(fact.validTo).getTime() >= asOfTime;
      return fromOk && toOk;
    }
    return true;
  });
};

export const timeline = async ({ vaultPath, subject = null }) => {
  const facts = await loadFacts(vaultPath);
  const items = subject
    ? facts.filter((fact) => normalizeText(fact.subject).includes(normalizeText(subject)) || normalizeText(fact.object).includes(normalizeText(subject)))
    : facts;
  return items.sort((a, b) => {
    const left = new Date(a.validFrom || a.createdAt).getTime();
    const right = new Date(b.validFrom || b.createdAt).getTime();
    return left - right;
  });
};

export const rebuildIndex = async ({ vaultPath }) => {
  const files = getVaultFiles(vaultPath);
  const records = await loadRecords(vaultPath);
  const index = {
    rebuiltAt: nowIso(),
    recordCount: records.length,
    entries: records.map((record) => ({
      id: record.id,
      title: record.title,
      tags: record.tags,
      tokens: tokenize([record.title, record.content, ...(record.tags ?? [])].join(' ')).slice(0, 80),
    })),
  };
  await writeJson(files.index, index);
  return index;
};

export const dedupRecords = async ({ vaultPath, threshold = 0.9, dryRun = true }) => {
  const files = getVaultFiles(vaultPath);
  const records = await loadRecords(vaultPath);
  const groups = new Map();
  for (const record of records) {
    const key = record.source || 'global';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  }

  const kept = [];
  const removed = [];

  const jaccard = (a, b) => {
    const setA = new Set(tokenize(a));
    const setB = new Set(tokenize(b));
    if (!setA.size || !setB.size) return 0;
    const intersection = [...setA].filter((token) => setB.has(token)).length;
    const union = new Set([...setA, ...setB]).size;
    return union ? intersection / union : 0;
  };

  for (const [, items] of groups.entries()) {
    const sorted = [...items].sort((a, b) => String(b.content).length - String(a.content).length);
    const bucket = [];
    for (const record of sorted) {
      const dup = bucket.find((candidate) => jaccard(candidate.content, record.content) >= threshold);
      if (dup) {
        removed.push(record);
      } else {
        bucket.push(record);
      }
    }
    kept.push(...bucket);
  }

  if (!dryRun) {
    const lines = kept.map((record) => JSON.stringify(record)).join('\n');
    await fs.writeFile(files.records, kept.length ? `${lines}\n` : '', 'utf8');
  }

  return {
    kept: kept.length,
    removed: removed.length,
    removedRecords: removed.map((record) => ({
      id: record.id,
      title: record.title,
      source: record.source,
      preview: recordSnippet(record),
    })),
  };
};

export const vaultStatus = async (homeDir = DEFAULT_HOME) => {
  const state = await loadState(homeDir);
  const vaults = await listVaults(homeDir);
  const active = vaults.find((vault) => path.resolve(vault.path) === path.resolve(state.activeVaultPath || ''));
  if (!active) {
    return {
      needsSetup: true,
      message: 'No active Vault is configured. Ask the user for a vault location or create one.',
      homeDir: resolveGlobalHome(homeDir),
      vaults,
    };
  }

  const records = await loadRecords(active.path);
  const facts = await loadFacts(active.path);
  const links = await loadLinks(active.path);
  const journal = await loadJournal(active.path);
  return {
    needsSetup: false,
    homeDir: resolveGlobalHome(homeDir),
    activeVault: active,
    vaults,
    counts: {
      records: records.length,
      facts: facts.length,
      links: links.length,
      journalEntries: journal.length,
    },
  };
};

export const exportVaultSnapshot = async (vaultPath) => {
  const files = getVaultFiles(vaultPath);
  const [records, facts, links, journal, metadata] = await Promise.all([
    loadRecords(vaultPath),
    loadFacts(vaultPath),
    loadLinks(vaultPath),
    loadJournal(vaultPath),
    readJson(files.metadata, {}),
  ]);
  return { metadata, records, facts, links, journal };
};

export const buildSummary = (values = []) =>
  values
    .filter(Boolean)
    .map((value) => String(value).trim())
    .filter(Boolean)
    .join(' | ');
