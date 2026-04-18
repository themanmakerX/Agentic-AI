# Superdeveloper for Codex

Guide for using the `superdeveloper` bundle with Codex-style skill discovery.

## Quick install

If you want the repository-provided install instructions directly, use:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/themanmakerX/Agentic-AI/refs/heads/main/skills/superdeveloper/.codex/INSTALL.md
```

## Manual install

### Prerequisites

- Codex installed locally
- Git available in `PATH`

### Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/themanmakerX/Agentic-AI.git ~/.codex/superdeveloper
   ```

2. Expose the packaged skills directory:

   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/superdeveloper/skills/superdeveloper/skills ~/.agents/skills/superdeveloper
   ```

3. Restart Codex so skills are rediscovered.

4. If you want multi-agent workflows, make sure your Codex setup supports subagents.

### Windows

Use a junction instead of a symlink:

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
cmd /c mklink /J "$env:USERPROFILE\.agents\skills\superdeveloper" "$env:USERPROFILE\.codex\superdeveloper\skills\superdeveloper\skills"
```

## What gets installed

The package exposes the skill folders under `skills/superdeveloper/skills/`. Once linked, Codex can discover the contained `SKILL.md` entry points on startup.

## Related docs

- Main package overview: `skills/superdeveloper/README.md`
- OpenCode install guide: `skills/superdeveloper/docs/README.opencode.md`
