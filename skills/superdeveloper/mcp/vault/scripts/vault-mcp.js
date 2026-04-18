import fs from 'fs/promises';
import path from 'path';
import readline from 'readline';
import os from 'os';
import {
  addFact,
  addJournalEntry,
  addLink,
  addRecord,
  chooseVault,
  createVault,
  dedupRecords,
  DEFAULT_HOME,
  ensureActiveVault,
  exportVaultSnapshot,
  getActiveVault,
  getVaultFiles,
  listVaults,
  queryFacts,
  rebuildIndex,
  searchRecords,
  setActiveVault,
  timeline,
  vaultStatus,
} from './vault-core.js';

const HOME = process.env.VAULT_HOME ? path.resolve(process.env.VAULT_HOME) : DEFAULT_HOME;

const parseArgs = () => {
  const args = process.argv.slice(2);
  const result = { vaultPath: null, autoCreate: false };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--vault' && args[i + 1]) {
      result.vaultPath = path.resolve(args[i + 1]);
      i += 1;
    } else if (arg === '--auto-create') {
      result.autoCreate = true;
    }
  }
  return result;
};

const cli = parseArgs();

const ensureRuntimeVault = async () => {
  if (cli.vaultPath) {
    return createVault({
      vaultPath: cli.vaultPath,
      name: path.basename(cli.vaultPath),
      homeDir: HOME,
      activate: true,
    });
  }
  const active = await getActiveVault(HOME);
  if (active) return active;
  if (!cli.autoCreate) return null;
  return createVault({
    vaultPath: path.join(os.homedir(), 'Vault'),
    name: 'Vault',
    homeDir: HOME,
    activate: true,
  });
};

const TOOLS = {
  vault_status: {
    description: 'Show the current vault, configured vaults, and whether setup is needed.',
    inputSchema: { type: 'object', properties: {} },
    handler: async () => vaultStatus(HOME),
  },
  vault_list_vaults: {
    description: 'List all known vaults and the active one.',
    inputSchema: { type: 'object', properties: {} },
    handler: async () => ({
      vaults: await listVaults(HOME),
      activeVault: await getActiveVault(HOME),
    }),
  },
  vault_create_vault: {
    description: 'Create a vault directory and activate it.',
    inputSchema: {
      type: 'object',
      properties: {
        vault_path: { type: 'string' },
        name: { type: 'string' },
        activate: { type: 'boolean' },
      },
      required: ['vault_path'],
    },
    handler: async ({ vault_path, name, activate }) =>
      createVault({
        vaultPath: vault_path,
        name: name || path.basename(vault_path),
        homeDir: HOME,
        activate: activate !== false,
      }),
  },
  vault_use_vault: {
    description: 'Switch the active vault to an existing vault path.',
    inputSchema: {
      type: 'object',
      properties: {
        vault_path: { type: 'string' },
      },
      required: ['vault_path'],
    },
    handler: async ({ vault_path }) => {
      const resolved = await setActiveVault({ vaultPath: vault_path, homeDir: HOME });
      return { activeVaultPath: resolved };
    },
  },
  vault_add_record: {
    description: 'Store a verbatim record in the active vault.',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        content: { type: 'string' },
        tags: { type: 'array', items: { type: 'string' } },
        source: { type: 'string' },
        kind: { type: 'string' },
      },
      required: ['content'],
    },
    handler: async (input) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return addRecord({
        vaultPath: active.path,
        title: input.title || '',
        content: input.content,
        tags: input.tags || [],
        source: input.source || '',
        kind: input.kind || 'record',
      });
    },
  },
  vault_ingest_text: {
    description: 'Ingest plain text with optional tags and source metadata.',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string' },
        content: { type: 'string' },
        tags: { type: 'array', items: { type: 'string' } },
        source: { type: 'string' },
      },
      required: ['content'],
    },
    handler: async (input) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      const record = await addRecord({
        vaultPath: active.path,
        title: input.title || '',
        content: input.content,
        tags: input.tags || [],
        source: input.source || '',
        kind: 'ingest',
      });
      await addJournalEntry({
        vaultPath: active.path,
        entryType: 'ingest',
        note: input.title ? `Ingested: ${input.title}` : 'Ingested text',
        metadata: { recordId: record.id, source: input.source || '' },
      });
      return record;
    },
  },
  vault_search: {
    description: 'Search the active vault.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string' },
        limit: { type: 'integer' },
        kind: { type: 'string' },
        tag: { type: 'string' },
      },
      required: ['query'],
    },
    handler: async ({ query, limit, kind, tag }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return {
        vault: active.name,
        results: await searchRecords({
          vaultPath: active.path,
          query,
          limit: limit || 5,
          kind: kind || null,
          tag: tag || null,
        }),
      };
    },
  },
  vault_get_record: {
    description: 'Fetch a single record by id.',
    inputSchema: {
      type: 'object',
      properties: {
        record_id: { type: 'string' },
      },
      required: ['record_id'],
    },
    handler: async ({ record_id }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      const { records } = getVaultFiles(active.path);
      const data = await fs.promises.readFile(records, 'utf8').catch(() => '');
      const found = data
        .split('\n')
        .filter(Boolean)
        .map((line) => JSON.parse(line))
        .find((record) => record.id === record_id);
      return found || { error: `Record not found: ${record_id}` };
    },
  },
  vault_add_fact: {
    description: 'Add a structured fact to the active vault.',
    inputSchema: {
      type: 'object',
      properties: {
        subject: { type: 'string' },
        predicate: { type: 'string' },
        object: { type: 'string' },
        valid_from: { type: 'string' },
        valid_to: { type: 'string' },
        confidence: { type: 'number' },
      },
      required: ['subject', 'predicate', 'object'],
    },
    handler: async (input) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return addFact({
        vaultPath: active.path,
        subject: input.subject,
        predicate: input.predicate,
        object: input.object,
        validFrom: input.valid_from || null,
        validTo: input.valid_to || null,
        confidence: input.confidence ?? 1,
      });
    },
  },
  vault_query_entity: {
    description: 'Query structured facts for an entity.',
    inputSchema: {
      type: 'object',
      properties: {
        subject: { type: 'string' },
        as_of: { type: 'string' },
        direction: { type: 'string' },
      },
      required: ['subject'],
    },
    handler: async ({ subject, as_of, direction }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return {
        subject,
        facts: await queryFacts({
          vaultPath: active.path,
          subject,
          asOf: as_of || null,
          direction: direction || 'both',
        }),
        timeline: await timeline({ vaultPath: active.path, subject }),
      };
    },
  },
  vault_add_link: {
    description: 'Add an explicit link between two records.',
    inputSchema: {
      type: 'object',
      properties: {
        from_record_id: { type: 'string' },
        to_record_id: { type: 'string' },
        label: { type: 'string' },
      },
      required: ['from_record_id', 'to_record_id'],
    },
    handler: async ({ from_record_id, to_record_id, label }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return addLink({
        vaultPath: active.path,
        fromRecordId: from_record_id,
        toRecordId: to_record_id,
        label: label || '',
      });
    },
  },
  vault_journal_write: {
    description: 'Write a checkpoint or session note into the active vault journal.',
    inputSchema: {
      type: 'object',
      properties: {
        session_id: { type: 'string' },
        entry_type: { type: 'string' },
        note: { type: 'string' },
      },
      required: ['note'],
    },
    handler: async ({ session_id, entry_type, note }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return addJournalEntry({
        vaultPath: active.path,
        sessionId: session_id || '',
        entryType: entry_type || 'checkpoint',
        note,
      });
    },
  },
  vault_journal_read: {
    description: 'Read recent journal entries.',
    inputSchema: {
      type: 'object',
      properties: {
        last_n: { type: 'integer' },
      },
    },
    handler: async ({ last_n }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      const { journal } = getVaultFiles(active.path);
      const entries = await fs.promises.readFile(journal, 'utf8').catch(() => '');
      const parsed = entries.split('\n').filter(Boolean).map((line) => JSON.parse(line));
      return {
        vault: active.name,
        entries: parsed.slice(Math.max(0, parsed.length - (last_n || 10))),
      };
    },
  },
  vault_checkpoint: {
    description: 'Store a checkpoint and optionally a short summary record.',
    inputSchema: {
      type: 'object',
      properties: {
        session_id: { type: 'string' },
        note: { type: 'string' },
        summary: { type: 'string' },
        source: { type: 'string' },
      },
      required: ['note'],
    },
    handler: async ({ session_id, note, summary, source }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      const journalEntry = await addJournalEntry({
        vaultPath: active.path,
        sessionId: session_id || '',
        entryType: 'checkpoint',
        note,
        metadata: { source: source || '' },
      });
      let record = null;
      if (summary && String(summary).trim()) {
        record = await addRecord({
          vaultPath: active.path,
          title: `Checkpoint ${journalEntry.createdAt}`,
          content: summary,
          tags: ['checkpoint'],
          source: source || '',
          kind: 'checkpoint',
        });
      }
      return { journalEntry, record };
    },
  },
  vault_rebuild_index: {
    description: 'Rebuild the derived search index for the active vault.',
    inputSchema: { type: 'object', properties: {} },
    handler: async () => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return rebuildIndex({ vaultPath: active.path });
    },
  },
  vault_dedup: {
    description: 'Deduplicate near-identical records.',
    inputSchema: {
      type: 'object',
      properties: {
        threshold: { type: 'number' },
        dry_run: { type: 'boolean' },
      },
    },
    handler: async ({ threshold, dry_run }) => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return dedupRecords({
        vaultPath: active.path,
        threshold: threshold ?? 0.9,
        dryRun: dry_run !== false,
      });
    },
  },
  vault_export_snapshot: {
    description: 'Export the current vault contents in one object.',
    inputSchema: { type: 'object', properties: {} },
    handler: async () => {
      const active = await ensureRuntimeVault();
      if (!active) return vaultStatus(HOME);
      return exportVaultSnapshot(active.path);
    },
  },
};

const handleRequest = async (request) => {
  const { method, params = {}, id } = request;
  if (method === 'initialize') {
    return {
      jsonrpc: '2.0',
      id,
      result: {
        protocolVersion: params.protocolVersion || '2025-11-25',
        capabilities: { tools: {} },
        serverInfo: {
          name: 'vault',
          version: '0.1.0',
        },
      },
    };
  }
  if (method === 'ping') {
    return { jsonrpc: '2.0', id, result: {} };
  }
  if (method === 'tools/list') {
    return {
      jsonrpc: '2.0',
      id,
      result: {
        tools: Object.entries(TOOLS).map(([name, tool]) => ({
          name,
          description: tool.description,
          inputSchema: tool.inputSchema,
        })),
      },
    };
  }
  if (method === 'tools/call') {
    const name = params.name;
    if (!TOOLS[name]) {
      return {
        jsonrpc: '2.0',
        id,
        error: { code: -32601, message: `Unknown tool: ${name}` },
      };
    }
    const args = params.arguments || {};
    try {
      const result = await TOOLS[name].handler(args);
      return {
        jsonrpc: '2.0',
        id,
        result: {
          content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
        },
      };
    } catch (error) {
      return {
        jsonrpc: '2.0',
        id,
        error: {
          code: -32000,
          message: error instanceof Error ? error.message : 'Internal Vault error',
        },
      };
    }
  }
  return {
    jsonrpc: '2.0',
    id,
    error: { code: -32601, message: `Unknown method: ${method}` },
  };
};

const main = async () => {
  await ensureRuntimeVault();
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of rl) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let request;
    try {
      request = JSON.parse(trimmed);
    } catch {
      continue;
    }
    const response = await handleRequest(request);
    if (response) {
      process.stdout.write(`${JSON.stringify(response)}\n`);
    }
  }
};

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exit(1);
});
