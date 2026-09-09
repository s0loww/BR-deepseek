---
description: "Automation script contract: DryRun/Apply, exit codes, reports, artifact integrity, credentials, idempotency. Load when writing or reviewing automation scripts, or when an artifact's integrity is fixed by a checksum. Триггеры: скрипт, автоматизация, мутации данных, отчёт скрипта, идемпотентность, манифест, контрольная сумма, целостность артефакта"
alwaysApply: false
kind: invariant
---

# Automation script contract

The rules below are mandatory for any script that automates changes to
data or system state. A script that does not meet the contract is not
accepted — regardless of the language or platform it is written in.

## Mutations only behind an explicit flag

By default the script runs in DryRun mode: it shows what it would change
but does not touch the data. Real application is enabled only by an
explicit flag (`-Apply`/`--apply` or an equivalent). A script without a
DryRun mode is not accepted.

## Honest exit codes

Code `0` means full success only. Partial success, skips, or warnings
return a non-zero code or an explicit final status in the output. Errors
are not swallowed silently — they surface in the return code and in the
report.

## Verifiable report

A mutating script writes a machine-readable report (CSV/JSON): what it
found, what it changed, what it skipped and why. The report is saved to
the project's log directory, not only printed to the console — otherwise
the result cannot be re-checked after the run.

## Artifact integrity

When an artifact's integrity is fixed by hashing its bytes — a checksum
manifest over reports, evidence, or reference files — pin line endings for
that artifact tree with a `.gitattributes` inside it. Otherwise
`core.autocrlf` rewrites the bytes on checkout and the hash holds only on the
machine that computed it. The failure is silent and delayed: it surfaces on
the first fresh clone, not when the manifest is written. Verify with
`git ls-files --eol <path>` — index and working tree must agree.

Pin the directories the project owns. Do not widen an attribute list that
belongs to someone else (a distribution, a vendored tree): a broad rule
rewrites foreign files with mixed endings without asking.

## Verification after Apply

After applying changes, the script re-reads the real state and compares it
with the expected result. The return code and the script's own report are
not taken at face value — verification comes from independently read data,
not from what the script reported about itself.

## Credentials

Secrets come only from a git-ignored environment file or from environment
variables. Forbidden: secrets in code, in command-line arguments, in
`echo`/logs/reports. When printing a connection string or a similar value,
the secret is masked (`***`).

## Idempotency

A repeated run with the same parameters does not break state. Before
making a change the script checks "already done?" and skips a step that
is already completed instead of blindly repeating the mutation.

## Structure: lib/ + domain folders

The reusable core (connection, wrappers, queries, export) lives in
`lib/`; one-off and domain scenarios live in per-task folders and include
`lib/` instead of duplicating it. Before writing a new script, first look
for an existing one or a sample in the existing folders.

## Who writes and who executes

Writing and changing a script is a task for medium/high-tier roles;
executing a ready, verified script is a task for a low-tier executor with
verification of the real logs. Details of role/tier resolution are in
`delegation.md`.
