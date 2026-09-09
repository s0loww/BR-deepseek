---
id: powershell-windows
name: powershell-windows
description: "Windows environment: PowerShell scripting rules for both Windows PowerShell 5.1 and PowerShell 7+. Use when running shell commands, Docker operations, or HTTP requests on Windows. Триггеры: PowerShell, шелл на Windows, команды Windows."
---

# PowerShell Windows — Scripting Rules

**Know your edition first.** `$PSVersionTable.PSVersion` — the rules below
differ between Windows PowerShell 5.1 (`powershell.exe`, default on
Windows) and PowerShell 7+ (`pwsh.exe`). When a script must run on both,
follow the 5.1-safe column.

## Core Principles

### 1. Command Separation
- PowerShell 7+: `&&` / `||` pipeline chain operators work as in bash.
- Windows PowerShell 5.1: `&&` is a parse error — use `;` (unconditional)
  or `if ($LASTEXITCODE -eq 0) { ... }` (conditional).
- 5.1-safe: `cd "<project-dir>"; ./build.ps1`

### 2. Path Quoting
- **Always use double quotes** for paths with spaces:
  ```powershell
  cd "<project-dir with spaces>"
  ```

### 3. Script Execution
- For .bat/.cmd files:
  ```powershell
  ./gradlew clean build
  .\gradlew.bat clean build
  ```

### 4. HTTP Requests
- `curl.exe` ships with Windows 10+ — call it with the explicit `.exe`
  suffix to bypass the 5.1 `curl` alias (which maps to Invoke-WebRequest
  with different flags).
- Portable alternative:
  ```powershell
  Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
  ```
- `-UseBasicParsing` is needed on 5.1 only; harmless (deprecated no-op) on 7+.

### 5. Waiting/Delays
- `timeout.exe` exists but breaks in non-interactive sessions ("input
  redirection is not supported"). In scripts always:
  ```powershell
  Start-Sleep -Seconds 10
  ```

### 6. JSON Handling
  ```powershell
  $response = Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
  $json = $response.Content | ConvertFrom-Json
  $json | ConvertTo-Json -Depth 3
  ```

### 7. Process Checking / Error Handling
  ```powershell
  Get-Process -Name "java" -ErrorAction SilentlyContinue
  ```

### 8. Docker Operations
- Specify the full path to compose files when running outside the project
  directory:
  ```powershell
  docker-compose -f "<project-dir>\docker-compose.yml" up -d
  docker-compose -f "<project-dir>\docker-compose.yml" down
  docker-compose -f "<project-dir>\docker-compose.yml" build --no-cache
  ```

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `&& is not recognized` | bash chaining on PowerShell 5.1 | `;` or upgrade to 7+ |
| `curl: parameter cannot be processed` | 5.1 `curl` alias → Invoke-WebRequest | call `curl.exe` explicitly |
| `timeout: input redirection not supported` | timeout.exe in non-interactive session | `Start-Sleep` |
| `Path not found` | missing quotes on a spaced path | wrap path in double quotes |

## Correct Command Examples

```powershell
# Change directory and build (5.1-safe)
cd "<project-dir>"; ./gradlew clean build -x test

# Wait and probe an endpoint
Start-Sleep -Seconds 10; Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing

# Check server status
$response = Invoke-WebRequest -Uri "http://localhost:9090/status" -UseBasicParsing
$json = $response.Content | ConvertFrom-Json
Write-Host "Transport: $($json.mcp.transport)"
```

Domain COM automation — see the stack rule in the corresponding overlay.
