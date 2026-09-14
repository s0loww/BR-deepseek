# 1C Web Manage — Web Publishing for 1C Information Bases

Publish and operate a 1C information base over HTTP via Apache (or IIS) for
thin web clients, OData, HTTP services and SOAP.

> **Note**: the `1c-web-ops` script family (`web-info` / `web-publish` /
> `web-stop` / `web-unpublish` / Playwright runner `run.mjs`) has **not been
> ported** — there are no scripts under `tools/`. This document describes the
> manual procedure built on the platform's own `webinst` utility (ships with
> every 1C installation) plus direct Apache control. Porting `1c-web-ops` is a
> tracked candidate (see distribution TODO).

The stable workflow stays the same:

```
inspect state → publish → smoke test → unpublish (or just stop Apache)
```

---

## Connection parameters

Resolve the target infobase from the project profile (the same source
`db-manage` uses; see db-manage.md "Connection parameters"): explicit
path/server from the user → alias → git-branch match → `default: true` entry.
If the profile is missing — stop and ask the user to register the base first.

**Credentials:** a publication can embed a user/password into `default.vrd` in
**plain text**. Per the script contract, do not put real passwords into files
that may be committed: keep `.vrd` files with embedded credentials outside the
repo (or in a git-ignored location) and prefer OS-level access control on the
publication directory.

---

## 1. Inspect state

- Apache process alive? `Get-Process -Name httpd -ErrorAction SilentlyContinue`
  (or check the service/port: `netstat -ano | findstr :<port>`).
- What is published? Read the publication blocks in `httpd.conf` and the
  `default.vrd` files they point to (`<point>` entries: application name, base
  connection string).
- Errors? Tail `logs/error.log` under the Apache root.

## 2. Publish — platform utility `webinst`

`webinst` lives in the platform `bin/` directory (resolve it the same way
db-manage resolves `-V8Path`).

```powershell
# File infobase
& "<v8-bin>\webinst.exe" -publish -apache24 `
    -wsdir <AppName> `
    -dir "<apache-htdocs>\<AppName>" `
    -connstr "File=""<infobase-dir>"";" `
    -confpath "<apache-root>\conf\httpd.conf"

# Server infobase
& "<v8-bin>\webinst.exe" -publish -apache24 `
    -wsdir <AppName> `
    -dir "<apache-htdocs>\<AppName>" `
    -connstr "Srvr=""<cluster>"";Ref=""<base-ref>"";" `
    -confpath "<apache-root>\conf\httpd.conf"
```

`webinst` generates `default.vrd`, adds the publication block to `httpd.conf`
and wires the platform web extension module. Restart Apache afterwards
(`httpd.exe -k restart` or restart the service).

**Idempotency:** re-running with the same `-wsdir` replaces the publication —
use that to switch the embedded user or refresh the module path after a
platform upgrade. Parallel publications of the same base under different users
(e.g. testing role-based access) — one publication per user, distinct
`-wsdir` names.

After success the endpoints are:

- Web client: `http://localhost:<port>/<AppName>`
- OData: `http://localhost:<port>/<AppName>/odata/standard.odata`
- HTTP services: `http://localhost:<port>/<AppName>/hs/<RootUrl>/...`
- Web services: `http://localhost:<port>/<AppName>/ws/<Name>?wsdl`

## 3. Stop without removing the publication

Stop Apache, keep `httpd.conf` entries and `default.vrd` in place; the next
start brings the publication back unchanged:

```powershell
& "<apache-root>\bin\httpd.exe" -k stop
```

Use when finishing the day, releasing the port, or before backing up file
infobases (avoids platform locks).

## 4. Unpublish

```powershell
& "<v8-bin>\webinst.exe" -delete -apache24 `
    -wsdir <AppName> `
    -confpath "<apache-root>\conf\httpd.conf"
```

Removes the publication block and the `.vrd`; the infobase itself is **not**
touched. Restart Apache if other publications must keep serving.

## 5. Smoke test

Minimal check after publishing — the endpoint answers and renders no platform
error banner:

```powershell
Invoke-WebRequest -Uri "http://localhost:<port>/<AppName>" -UseBasicParsing | Select-Object StatusCode
```

For a real UI smoke (start page renders, login works) use the test contour of
`agent-1c` (see `tools/agent-1c/DEPLOYMENT.md`) or drive a browser
manually. Scripted browser scenarios previously covered by the unported
Playwright runner should live in the project's own test contour until
`1c-web-ops` is restored.

---

## When to delegate to `metadata-manager`

- Multiple operations chained (publish → test → unpublish).
- Configuration changes that require platform restart in between.
- Custom Apache layout or non-default port mapping.

For a single read-only state inspection or a one-shot smoke probe, run the
commands directly — delegation overhead is not worth it.
