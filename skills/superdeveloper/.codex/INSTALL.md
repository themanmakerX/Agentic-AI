# Installing Superdeveloper for Codex

Enable superdeveloper skills in Codex via native skill discovery. Just clone and symlink.

## Prerequisites

- Git

## Installation

1. **Clone the superdeveloper repository:**
   ```bash
   git clone https://github.com/themanmakerX/Agentic-AI.git ~/.codex/superdeveloper
   ```

2. **Create the skills symlink:**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/superdeveloper/skills ~/.agents/skills/superdeveloper
   ```

   **Windows (PowerShell):**
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\superdeveloper" "$env:USERPROFILE\.codex\superdeveloper\skills"
   ```

3. **Restart Codex** (quit and relaunch the CLI) to discover the skills.

## Migrating from old bootstrap

If you installed superdeveloper before native skill discovery, you need to:

1. **Update the repo:**
   ```bash
   cd ~/.codex/superdeveloper && git pull
   ```

2. **Create the skills symlink** (step 2 above) - this is the new discovery mechanism.

3. **Remove the old bootstrap block** from `~/.codex/AGENTS.md` - any block referencing `superdeveloper-codex bootstrap` is no longer needed.

4. **Restart Codex.**

## Verify

```bash
ls -la ~/.agents/skills/superdeveloper
```

You should see a symlink (or junction on Windows) pointing to your superdeveloper skills directory.

## Updating

```bash
cd ~/.codex/superdeveloper && git pull
```

Skills update instantly through the symlink.

## Uninstalling

```bash
rm ~/.agents/skills/superdeveloper
```

Optionally delete the clone: `rm -rf ~/.codex/superdeveloper`.
