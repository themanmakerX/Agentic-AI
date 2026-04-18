import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import {
  addJournalEntry,
  addRecord,
  DEFAULT_HOME,
  ensureActiveVault,
  vaultStatus,
} from './vault-core.js';

const HOME = process.env.VAULT_HOME ? path.resolve(process.env.VAULT_HOME) : DEFAULT_HOME;

const readStdin = async () => {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString('utf8').trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
};

const sessionId = (input) =>
  String(input.session_id || input.sessionId || input.session || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '');

const transcriptToText = async (transcriptPath) => {
  if (!transcriptPath) return '';
  const resolved = path.resolve(transcriptPath);
  const ext = path.extname(resolved).toLowerCase();
  try {
    const raw = await fs.readFile(resolved, 'utf8');
    if (ext === '.jsonl' || ext === '.json') {
      const lines = raw.split('\n').filter(Boolean);
      const snippets = [];
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          const text = entry?.message?.content || entry?.payload?.message || entry?.text;
          if (typeof text === 'string' && text.trim()) {
            snippets.push(text.trim());
          }
        } catch {
          // ignore
        }
      }
      return snippets.slice(-40).join('\n');
    }
    return raw;
  } catch {
    return '';
  }
};

const emit = async (payload) => {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
};

const run = async () => {
  const command = process.argv[2] || 'session-start';
  const input = await readStdin();
  const active = await ensureActiveVault(HOME);

  if (!active.active) {
    await emit(await vaultStatus(HOME));
    return;
  }

  const sid = sessionId(input);
  const transcript = await transcriptToText(input.transcript_path || input.transcriptPath || '');
  const title = input.title || input.session_title || `${command} checkpoint`;
  const note = input.note || `${command} for ${sid}`;

  if (transcript) {
    await addRecord({
      vaultPath: active.active.path,
      title,
      content: transcript,
      tags: ['hook', command],
      source: input.transcript_path || input.transcriptPath || '',
      kind: 'hook-transcript',
      metadata: { sessionId: sid, hook: command },
    });
  }

  await addJournalEntry({
    vaultPath: active.active.path,
    sessionId: sid,
    entryType: command,
    note,
    metadata: {
      transcriptPath: input.transcript_path || input.transcriptPath || '',
    },
  });

  await emit({
    ok: true,
    command,
    sessionId: sid,
    wroteTranscript: Boolean(transcript),
    vault: active.active.name,
  });
};

run().catch(async (error) => {
  await emit({ ok: false, error: error instanceof Error ? error.message : String(error) });
  process.exit(1);
});
