# Role registry

Six roles for the base build. Each one is a markdown file in
`agents/roles/<role>.md`, installed into the target project as
`.kun/agents/<role>.md`.

| role | model | effort | toolPolicy | purpose |
| --- | --- | --- | --- | --- |
| explorer | flash | high | readOnly | Codebase reconnaissance, search, subsystem map — no edits |
| planner | pro | max | inherit | Task decomposition, implementation plan, risks, dependencies |
| developer | pro | high | inherit | Code implementation from a ready plan |
| error-fixer | flash | high | inherit | Fast targeted error fixing, minimal edits, no architectural changes |
| tester | flash | high | inherit | Test runs, behavior verification, evidence collection |
| code-reviewer | pro | high | readOnly | Code review — only on an explicit user request |

`flash` / `pro` resolve through `install/model-map.yaml`. `toolPolicy` is a
Kun frontmatter field: `readOnly` — read and search only; `inherit` — the
session's full tool set.

## Where the model and the effort actually come from

**Kun does not read a model or an effort from the role file.** The workspace
markdown overlay carries `id`, `name`, `description`, `mode`, `toolPolicy`,
`color`, `allowedTools` and `blockedTools` — and nothing else. A subagent
runs on the session model unless a per-agent override is set in the GUI
(Settings → Agents), so the table above is a **configuration
recommendation**, not something the file enforces.

Practical consequence: pick the session model for the heaviest role you plan
to run, and override the light roles downward in the GUI. Do not assume a
role file demotes itself — it cannot.

## Effort semantics on DeepSeek

The scale is `off | high | max` (Kun's default is `max`), which is coarser
than a four-step scale. Use it as:

- `max` — planning, architecture, an unclear bug, a release-gate review.
- `high` — the working default: implementation from a plan, targeted fixes,
  test runs, reconnaissance.
- `off` — mechanical passes where deliberation buys nothing (running a ready
  script, collecting logs, bulk renames).

`max` as a blanket default is not free: it is the most expensive step and it
does not improve mechanical work. Set the session to `high` and escalate
deliberately.

## Roles that are not in the base build

`analytic`, `architect`, `arch-reviewer`, `refactoring`, `doc-writer`,
`metadata-manager`, `performance-optimizer` — the upstream distribution has
them; this build does not. Their work stays with the orchestrator until
there is evidence the model holds a longer role chain. Add a role only when
a concrete task keeps hitting the gap.
