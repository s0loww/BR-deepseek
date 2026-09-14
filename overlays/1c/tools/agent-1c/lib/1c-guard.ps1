<#
    1c-guard.ps1 — сторож над запусками 1cv8.

    Решает две задачи, из-за которых прогон без человека у экрана ломался.

    1. ВЗАИМНОЕ ИСКЛЮЧЕНИЕ ПО БАЗЕ.
       LoadConfigFromFiles/UpdateDBCfg и прогон тестов монопольны: два
       параллельных прогона по одной ИБ получают блокировку конфигурации и
       невнятную ошибку, в которой разбираются дорого и обычно неверно.
       Лок берёт СКРИПТ, а не исполнитель по инструкции: забыть его нельзя, а
       освобождается он при выходе процесса, включая аварийный (ОС закрывает
       дескриптор файла).

    2. СТОРОЖ НАД ПРОЦЕССОМ.
       Живой случай: деплой встал намертво — 1cv8 раздулся до 20 ГБ, CPU в
       нуле, /Out-лог нулевой длины. Причиной было скрытое модальное окно
       «недостаточность памяти»: его нашли глазами и сняли процесс руками.
       Без человека у экрана этого не происходит, а следом за памятью ложатся
       и остальные сервисы машины. Поэтому запуск идёт без -Wait, с опросом
       процесса: потолок памяти, потолок времени, детект зависания и детект
       появившегося окна.

    Подключение:  . (Join-Path $PSScriptRoot 'lib\1c-guard.ps1')
                  Скрипты проекта, ходящие в ту же ИБ мимо agent-1c, обязаны
                  подключать ЭТОТ же файл: лок, накрывающий один путь из
                  двух, не гарантирует ничего.
    Совместимость: Windows PowerShell 5.1 и PowerShell 7+.
#>

# Здесь намеренно НЕТ Set-StrictMode: файл подключается через dot-source, и
# режим протёк бы в вызывающий скрипт, поломав в нём обращения к необъявленным
# свойствам (agent-1c.ps1 так работает с профилем).

function Get-1CGuardSetting {
    <# Значение по умолчанию можно переопределить переменной окружения,
       не правя скрипты — удобно при подборе порогов. #>
    param([string]$Name, $Default)

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function Get-1CLockDir {
    # ProgramData — общий для всех сессий пользователя; при отсутствии прав
    # откатываемся в профиль (все агенты работают под одним пользователем).
    $dir = Join-Path $env:ProgramData '1c-agent-locks'
    try {
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        return $dir
    } catch {
        $dir = Join-Path $env:LOCALAPPDATA '1c-agent-locks'
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        return $dir
    }
}

function Get-1CLockKey {
    <# Ключ лока — НА БАЗУ, а не глобальный: разным ИБ пересекаться незачем.
       Хвост пути оставляем читаемым, чтобы в каталоге локов было видно, что
       чем занято; хэш добавляем от коллизий. #>
    param([Parameter(Mandatory = $true)][string]$Target)

    $normalized = $Target.Trim().ToLowerInvariant() -replace '[\\/]+$', ''
    $md5 = [System.Security.Cryptography.MD5]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $hash = ([BitConverter]::ToString($md5.ComputeHash($bytes)) -replace '-', '').Substring(0, 10).ToLowerInvariant()
    } finally {
        $md5.Dispose()
    }

    $slug = ($normalized -replace '[^a-z0-9]+', '-').Trim('-')
    if ($slug.Length -gt 40) { $slug = $slug.Substring($slug.Length - 40) }
    if ([string]::IsNullOrWhiteSpace($slug)) { $slug = 'base' }

    return "$slug-$hash"
}

function Write-1CGuardLog {
    param([string]$Path, [string]$Text)

    if ([string]::IsNullOrWhiteSpace($Path)) { return }
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $Text
    # Очередь пишут несколько процессов сразу — короткий retry вместо падения.
    for ($i = 0; $i -lt 25; $i++) {
        try {
            Add-Content -LiteralPath $Path -Encoding UTF8 -Value $line
            return
        } catch {
            Start-Sleep -Milliseconds 120
        }
    }
}

function Enter-1CBaseLock {
    <#
        Занимает базу. Возвращает объект лока для Exit-1CBaseLock.
        При превышении ожидания бросает исключение с именем держателя —
        агент увидит внятную причину и вернёт задачу в очередь, а не будет
        гадать над ошибкой платформы.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$Target,
        [string]$Owner = '',
        [int]$WaitMinutes = [int](Get-1CGuardSetting 'AGENT1C_LOCK_WAIT_MIN' 15),
        [string]$LogPath = ''
    )

    if ([string]::IsNullOrWhiteSpace($Owner)) {
        # Внешний оркестратор может пометить прогон своим идентификатором —
        # тогда в очереди видно не только пользователя и pid.
        $tag = Get-1CGuardSetting 'AGENT1C_RUN_ID' ''
        $Owner = "$env:USERNAME/pid=$PID"
        if (-not [string]::IsNullOrWhiteSpace($tag)) { $Owner += "/run=$tag" }
    }

    $dir = Get-1CLockDir
    $key = Get-1CLockKey -Target $Target
    $lockPath = Join-Path $dir "$key.lock"
    $ownerPath = Join-Path $dir "$key.owner"
    $queuePath = Join-Path $dir "$key.queue.log"

    $deadline = (Get-Date).AddMinutes($WaitMinutes)
    $announced = $false
    $waitStarted = Get-Date

    while ($true) {
        try {
            # FileShare::None — настоящий межпроцессный мьютекс. Дескриптор
            # держим открытым всё время работы; смерть процесса освобождает его.
            $stream = [System.IO.File]::Open(
                $lockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None)

            # Держателя пишем в ОТДЕЛЬНЫЙ файл: сам .lock открыт эксклюзивно и
            # ожидающие его прочитать не смогут.
            try {
                Set-Content -LiteralPath $ownerPath -Encoding UTF8 -Value @(
                    "owner=$Owner",
                    "target=$Target",
                    "since=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
                )
            } catch { }

            $waited = [int]((Get-Date) - $waitStarted).TotalSeconds
            Write-1CGuardLog -Path $queuePath -Text "ACQUIRED by $Owner (ожидание ${waited}s)"
            if ($LogPath) { Write-1CGuardLog -Path $LogPath -Text "LOCK_ACQUIRED key=$key ожидание=${waited}s" }

            return [pscustomobject]@{
                Key       = $key
                Target    = $Target
                Owner     = $Owner
                Stream    = $stream
                LockPath  = $lockPath
                OwnerPath = $ownerPath
                QueuePath = $queuePath
                LogPath   = $LogPath
            }
        } catch [System.IO.IOException] {
            if (-not $announced) {
                $holder = '<неизвестен>'
                try {
                    if (Test-Path -LiteralPath $ownerPath) {
                        $holder = ((Get-Content -LiteralPath $ownerPath -Encoding UTF8) -join '; ')
                    }
                } catch { }
                Write-1CGuardLog -Path $queuePath -Text "WAITING $Owner (держит: $holder)"
                if ($LogPath) { Write-1CGuardLog -Path $LogPath -Text "LOCK_WAIT key=$key держит: $holder" }
                Write-Host "База занята другим прогоном, жду до $WaitMinutes мин. Держит: $holder"
                $announced = $true
            }

            if ((Get-Date) -gt $deadline) {
                Write-1CGuardLog -Path $queuePath -Text "TIMEOUT $Owner (ждал ${WaitMinutes}m)"
                if ($LogPath) { Write-1CGuardLog -Path $LogPath -Text "LOCK_TIMEOUT key=$key" }
                throw "База занята другим прогоном дольше $WaitMinutes мин: $Target. Очередь: $queuePath. Верни задачу в очередь и повтори позже."
            }

            Start-Sleep -Seconds 5
        }
    }
}

function Exit-1CBaseLock {
    param($Lock)

    if (-not $Lock) { return }
    try { $Lock.Stream.Close() } catch { }
    try { $Lock.Stream.Dispose() } catch { }
    try { if (Test-Path -LiteralPath $Lock.OwnerPath) { Remove-Item -LiteralPath $Lock.OwnerPath -Force -ErrorAction SilentlyContinue } } catch { }
    Write-1CGuardLog -Path $Lock.QueuePath -Text "RELEASED by $($Lock.Owner)"
    if ($Lock.LogPath) { Write-1CGuardLog -Path $Lock.LogPath -Text "LOCK_RELEASED key=$($Lock.Key)" }
}

function Stop-1CProcessTree {
    param([int]$ProcessId)

    # /T — вместе с потомками: 1cv8 порождает вспомогательные процессы,
    # которые иначе останутся держать базу.
    try { & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null } catch { }
    for ($i = 0; $i -lt 40; $i++) {
        if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Invoke-Guarded1C {
    <#
        Запускает 1cv8 (или vrunner) под присмотром. Вместо Start-Process -Wait,
        который висит бесконечно.

        Возвращает объект: ExitCode, Killed, Reason, PeakPrivateGb, DurationSec.
        ExitCode при убийстве = -1.

        Пороги памяти намеренно двухступенчатые:
          * HardMemoryGb — режем безусловно, это защита машины: в наблюдавшемся
            случае следом за 1С полегли остальные сервисы хоста;
          * SoftMemoryGb — режем ТОЛЬКО если процесс при этом стоит (не тратит
            CPU). Ровно такая сигнатура была у зависшего на модальном окне
            деплоя, а честно работающий большой деплой CPU потребляет и под
            мягкий порог не подпадает.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [string]$Label = '1cv8',
        [int]$TimeoutMinutes = [int](Get-1CGuardSetting 'AGENT1C_CMD_TIMEOUT_MIN' 25),
        [double]$SoftMemoryGb = [double](Get-1CGuardSetting 'AGENT1C_SOFT_MEM_GB' 6),
        [double]$HardMemoryGb = [double](Get-1CGuardSetting 'AGENT1C_HARD_MEM_GB' 12),
        [int]$StallMinutes = [int](Get-1CGuardSetting 'AGENT1C_STALL_MIN' 3),
        # Для процессов-обёрток (vrunner) память и простой мерить бессмысленно:
        # реальную работу делают дочерние 1cv8, а сам раннер их только ждёт —
        # он всегда выглядит "пустым и стоящим". Там остаётся только таймаут.
        [switch]$TimeoutOnly,
        [string]$LogPath = '',
        [switch]$Hidden,
        [string]$RedirectStandardOutput = '',
        [string]$RedirectStandardError = ''
    )

    $startParams = @{
        FilePath     = $FilePath
        ArgumentList = $ArgumentList
        PassThru     = $true
    }
    if ($Hidden) { $startParams['WindowStyle'] = 'Hidden' } else { $startParams['NoNewWindow'] = $true }
    if ($RedirectStandardOutput) { $startParams['RedirectStandardOutput'] = $RedirectStandardOutput }
    if ($RedirectStandardError) { $startParams['RedirectStandardError'] = $RedirectStandardError }

    $started = Get-Date
    $process = Start-Process @startParams

    # Обращение к Handle СРАЗУ после старта обязательно: объект от
    # Start-Process -PassThru без этого не сохраняет дескриптор процесса, и
    # после WaitForExit свойство ExitCode отдаёт $null вместо кода. Проверка
    # "$guard.ExitCode -ne 0" на таком $null истинна всегда — успешный запуск
    # приезжает наверх как "завершился с кодом .". Живой случай: load отработал
    # за 24 с, лог пуст, а деплой объявлен упавшим и /UpdateDBCfg не выполнился.
    try { $null = $process.Handle } catch { }

    Write-1CGuardLog -Path $LogPath -Text "GUARD_START $Label pid=$($process.Id) timeout=${TimeoutMinutes}m soft=${SoftMemoryGb}GB hard=${HardMemoryGb}GB"

    $peakGb = 0.0
    $sampleAt = Get-Date
    $sampleCpu = 0.0
    $stallSeconds = 0.0
    $dialogLogged = $false
    $killReason = ''

    while ($true) {
        Start-Sleep -Seconds 3
        try { $process.Refresh() } catch { break }
        if ($process.HasExited) { break }

        try {
            $privateGb = $process.PrivateMemorySize64 / 1GB
            $cpuSeconds = $process.TotalProcessorTime.TotalSeconds
        } catch {
            break   # процесс исчез между Refresh и чтением счётчиков
        }

        if ($privateGb -gt $peakGb) { $peakGb = $privateGb }

        # Окно наблюдения за CPU — 30 с: на трёхсекундном интервале честно
        # работающий процесс тоже может не набрать секунды процессорного времени.
        $windowSeconds = ((Get-Date) - $sampleAt).TotalSeconds
        if ($windowSeconds -ge 30) {
            if (($cpuSeconds - $sampleCpu) -lt 1) { $stallSeconds += $windowSeconds } else { $stallSeconds = 0 }
            $sampleAt = Get-Date
            $sampleCpu = $cpuSeconds
        }

        # Появившееся окно в пакетном режиме DESIGNER — почти наверняка модальный
        # диалог. НЕ убиваем по одному этому признаку (нет уверенности, что
        # платформа не создаёт окно штатно), но пишем заголовок в лог: утром
        # видно причину, не пришлось бы искать окно глазами.
        if (-not $dialogLogged) {
            try {
                if ($process.MainWindowHandle -ne [IntPtr]::Zero) {
                    $title = $process.MainWindowTitle
                    if ([string]::IsNullOrWhiteSpace($title)) { $title = '<без заголовка>' }
                    Write-1CGuardLog -Path $LogPath -Text "GUARD_DIALOG $Label окно появилось: $title"
                    $dialogLogged = $true
                }
            } catch { }
        }

        $elapsedMin = ((Get-Date) - $started).TotalMinutes

        if (-not $TimeoutOnly -and $privateGb -ge $HardMemoryGb) {
            $killReason = "memory-hard: $([math]::Round($privateGb,1)) ГБ >= $HardMemoryGb ГБ"
        } elseif (-not $TimeoutOnly -and $privateGb -ge $SoftMemoryGb -and $stallSeconds -ge ($StallMinutes * 60)) {
            $killReason = "memory-stalled: $([math]::Round($privateGb,1)) ГБ и без CPU $([int]$stallSeconds) с"
        } elseif ($elapsedMin -ge $TimeoutMinutes) {
            $killReason = "timeout: $([int]$elapsedMin) мин >= $TimeoutMinutes мин"
        }

        if ($killReason) {
            $extra = ''
            if ($dialogLogged) { $extra = ' (было замечено окно — вероятен модальный диалог)' }
            Write-1CGuardLog -Path $LogPath -Text "GUARD_KILL $Label $killReason$extra"
            Write-Host "СТОРОЖ: снимаю $Label — $killReason$extra"
            [void](Stop-1CProcessTree -ProcessId $process.Id)
            break
        }
    }

    $durationSec = [int]((Get-Date) - $started).TotalSeconds
    $exitCode = -1
    if (-not $killReason) {
        try { $process.WaitForExit() } catch { }
        try { $exitCode = $process.ExitCode } catch { $exitCode = -1 }
    }

    Write-1CGuardLog -Path $LogPath -Text ("GUARD_END $Label exit=$exitCode длительность=${durationSec}s пик памяти=" + [math]::Round($peakGb, 2) + 'ГБ')

    return [pscustomobject]@{
        ExitCode      = $exitCode
        Killed        = [bool]$killReason
        Reason        = $killReason
        PeakPrivateGb = [math]::Round($peakGb, 2)
        DurationSec   = $durationSec
        DialogSeen    = $dialogLogged
    }
}
