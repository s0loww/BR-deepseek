# Role registry — 1C overlay

Thirteen roles. In a 1C project they are installed into `.kun/agents/`
**instead of** the base roles: the seven base ids (`explorer`, `planner`,
`developer`, `error-fixer`, `tester`, `code-reviewer`, `doc-writer`) are
replaced by their 1C versions, and six roles are added.

| role | model | effort | toolPolicy | blockedTools | purpose |
| --- | --- | --- | --- | --- | --- |
| explorer | flash | high | inherit | edit, write, bash | Reconnaissance of 1C code and metadata through RLM — no edits |
| planner | pro | max | inherit | — | Decomposition, implementation plan, risks |
| developer | pro | high | inherit | — | BSL code from a ready plan |
| error-fixer | flash | high | inherit | — | Targeted fix of a 1C error, minimal diff |
| tester | flash | high | inherit | — | Deploy to the test infobase and behaviour checks |
| code-reviewer | pro | high | inherit | edit, write, bash | Code review on explicit request |
| doc-writer | pro | high | inherit | — | User and administrator documentation |
| analytic | pro | high | inherit | — | Requirements, specifications in 1C terms; no code |
| architect | pro | max | inherit | — | Design of a significant change |
| arch-reviewer | pro | high | inherit | edit, write, bash | Review of architectural decisions before implementation |
| refactoring | pro | high | inherit | — | Dead code, duplicates, performance fixes by recommendation |
| metadata-manager | pro | high | inherit | — | Metadata structure through the `1c-metadata-manage` skill |
| performance-optimizer | pro | max | inherit | edit, write | Bottlenecks from evidence (technical journal, measurements); recommendations only |

## Why no role is `readOnly`

In Kun `toolPolicy: readOnly` means *read / grep / find / ls — no MCP, no
skills*. 1C navigation in this build is the RLM MCP server, so a readOnly
explorer would be blind exactly where it is needed. Roles that must not edit
are `inherit` with Kun's built-in write tools blocked. `ci/check.py` rejects
`readOnly` on overlay roles.

What this does **not** block: RLM's own mutating actions (`rlm_projects`
add / remove / rename / update, `rlm_index` build / update / drop). Those
are gated by the project password on the RLM server and by an explicit line
in every role's Boundaries; the password never reaches the agent unless the
user types it in.

`performance-optimizer` keeps `bash`: analysing a technical journal means
aggregating large log files with scripts. Its Boundaries restrict `bash` to
reading and writing into a scratch directory outside the sources.

## Model and effort

Kun does not read model or effort from a role file — see `agents/ROLES.md`
of the base. The columns are the configuration to set per agent in
Settings → Agents.

Mapping from the upstream tiers: the upstream `high` tier and roles that
produce a design or a plan go to `pro`; mechanical roles (reconnaissance,
targeted fixes, test runs) go to `flash`, as in the base.
`metadata-manager` sits on `pro` although upstream keeps it on the middle
tier: its output is XML that the platform either loads or rejects, and a
rejected load costs a deploy cycle. `performance-optimizer` gets `max`:
locating a bottleneck from evidence is the kind of unclear problem `max` is
for.

The six added roles are not yet measured on DeepSeek. Base-build caution
applies: if a role chain does not hold, keep the work with the orchestrator
and drop the role from `.kun/agents/`.
