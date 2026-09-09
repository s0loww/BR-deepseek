# Layout in the target project

Source of content: this repository. This file says only **where** the
content goes and in **what format**.

Target: **Kun** (desktop GUI or TUI) running DeepSeek. Paths verified
against Kun's own contract — see `docs/kun-contract.md`.

## Project root

- `AGENTS.md` — the root contract. Kun reads it natively and injects it into
  **every turn** when "AGENTS.md instructions" is enabled in Settings.

  **⚠ Consequence:** everything in `AGENTS.md` is paid for on every turn.
  Keep it to the contract plus the rule index; rule bodies stay in `rules/`
  and are read on demand.

- `rules/` — rule bodies, read lazily via the Rule Index in `AGENTS.md`.
  Plain markdown; nothing scans this directory automatically, which is the
  point.

- `CLAUDE.md` — **not created.** Kun reads `AGENTS.md` directly; a second
  instruction file is a second source of truth.

## `.kun/`

- `.kun/agents/<role>.md` — one file per role, copied from `agents/roles/`.
  Frontmatter fields Kun actually reads:

  | field | values | meaning |
  | --- | --- | --- |
  | `id` | slug | agent id, must be unique |
  | `name` | string | display name |
  | `description` | string | shown in the catalog; carries the routing terms |
  | `mode` | `subagent` \| `primary` \| `all` | where the role can run |
  | `toolPolicy` | `readOnly` \| `inherit` | read-only vs the session's tools |
  | `color` | hex | catalog color, optional |
  | `allowedTools` / `blockedTools` | string[] | optional per-role tool lists |

  **⚠ Gotcha:** there is **no** `model` or `effort` field. A role runs on the
  session model unless overridden per agent in Settings → Agents. The tiers
  in `agents/ROLES.md` are a configuration recommendation, not something the
  file enforces.

- `.kun/skills/<skill>/SKILL.md` — copied from `skills/`. Kun also scans
  `.claude/skills`, `.codex/skills`, `.agents/skills` and `skills/` as
  conventional roots, so skills written for other harnesses work unchanged;
  `.kun/skills` is the native one and this build uses it.

- `.kun/project.json` — **not created in the base build.** It is the
  project-level MCP + skills policy. When MCP is added later: `version: 1`,
  `mcp.servers`, `skills.{enabled,includeConventional,roots,disabledIds}`,
  and it must be approved manually in Settings → Agents → Project MCP &
  Skills (Kun binds the approval to a SHA-256 digest of the file; a
  repository cannot approve itself).

## Not installed by this build

- **Hooks.** Kun's hook engine mirrors the Claude Code protocol (JSON on
  stdin, exit 2 blocks, JSON on stdout) across six phases — PreToolUse,
  PostToolUse, UserPromptSubmit, TurnStart, TurnEnd, PreCompact — but it is
  configured in the **machine-global** `~/.kun/data/config.json`, not in the
  repository. An installer cannot put a hook into the project, so the rule
  reminder that a hook would inject lives in the `AGENTS.md` rule index
  instead. A user who wants the hook adds it to their own config by hand.

- **Slash commands.** Kun's slash commands are built in; there is no
  file-based custom command directory. Commands from the upstream
  distribution are not ported — the equivalent work is a skill or a rule.

- **MCP servers.** Out of scope for the base build by decision, not by
  limitation.
