import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import {
  addFact,
  addJournalEntry,
  addLink,
  addRecord,
  createVault,
  dedupRecords,
  DEFAULT_HOME,
  ensureActiveVault,
  exportVaultSnapshot,
  getActiveVault,
  listVaults,
  queryFacts,
  rebuildIndex,
  searchRecords,
  setActiveVault,
  timeline,
  vaultStatus,
} from './vault-core.js';

const HOME = process.env.VAULT_HOME ? path.resolve(process.env.VAULT_HOME) : DEFAULT_HOME;

const print = (value) => {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
};

const requireActiveVault = async () => {
  const active = (await ensureActiveVault(HOME)).active;
  if (!active) {
    return { active: null, fallback: await vaultStatus(HOME) };
  }
  return { active, fallback: null };
};

const readArgs = () => {
  const args = process.argv.slice(2);
  const command = args.shift();
  const out = { command, flags: {}, positionals: [] };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith('--')) {
        out.flags[key] = next;
        i += 1;
      } else {
        out.flags[key] = true;
      }
    } else {
      out.positionals.push(arg);
    }
  }
  return out;
};

const main = async () => {
  const { command, flags, positionals } = readArgs();

  switch (command) {
    case 'status':
      print(await vaultStatus(HOME));
      return;
    case 'list-vaults':
      print({ vaults: await listVaults(HOME), activeVault: await getActiveVault(HOME) });
      return;
    case 'create-vault':
      print(
        await createVault({
          vaultPath: flags.path ? path.resolve(flags.path) : path.join(os.homedir(), 'Vault'),
          name: flags.name || path.basename(flags.path || 'Vault'),
          homeDir: HOME,
          activate: flags.activate !== 'false',
        }),
      );
      return;
    case 'use-vault':
      print({ activeVaultPath: await setActiveVault({ vaultPath: flags.path, homeDir: HOME }) });
      return;
    case 'search': {
      const { active, fallback } = await requireActiveVault();
      if (!active) {
        print(fallback);
        return;
      }
      const query = positionals.join(' ');
      print(
        await searchRecords({
          vaultPath: active.path,
          query,
          limit: Number(flags.limit || 5),
        }),
      );
      return;
    }
    case 'add-record':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await addRecord({
          vaultPath: active.path,
          title: flags.title || '',
          content: positionals.join(' '),
          tags: flags.tags ? String(flags.tags).split(',') : [],
          source: flags.source || '',
        }),
      );
      return;
      }
    case 'add-fact':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await addFact({
          vaultPath: active.path,
          subject: flags.subject,
          predicate: flags.predicate,
          object: flags.object,
          validFrom: flags.valid_from || null,
          validTo: flags.valid_to || null,
          confidence: Number(flags.confidence || 1),
        }),
      );
      return;
      }
    case 'add-link':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await addLink({
          vaultPath: active.path,
          fromRecordId: flags.from,
          toRecordId: flags.to,
          label: flags.label || '',
        }),
      );
      return;
      }
    case 'journal':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await addJournalEntry({
          vaultPath: active.path,
          sessionId: flags.session || '',
          entryType: flags.type || 'checkpoint',
          note: positionals.join(' '),
        }),
      );
      return;
      }
    case 'query-entity':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await queryFacts({
          vaultPath: active.path,
          subject: flags.subject,
          asOf: flags.as_of || null,
          direction: flags.direction || 'both',
        }),
      );
      return;
      }
    case 'timeline':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
        print(await timeline({ vaultPath: active.path, subject: flags.subject || null }));
      }
      return;
    case 'rebuild-index':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
        print(await rebuildIndex({ vaultPath: active.path }));
      }
      return;
    case 'dedup':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
      print(
        await dedupRecords({
          vaultPath: active.path,
          threshold: Number(flags.threshold || 0.9),
          dryRun: flags.dry_run !== 'false',
        }),
      );
      return;
      }
    case 'snapshot':
      {
        const { active, fallback } = await requireActiveVault();
        if (!active) {
          print(fallback);
          return;
        }
        print(await exportVaultSnapshot(active.path));
      }
      return;
    default:
      print(await vaultStatus(HOME));
  }
};

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exit(1);
});
