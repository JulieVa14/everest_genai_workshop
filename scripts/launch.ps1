<#
.SYNOPSIS
Launch the localhost workshop. Ctrl+C stops both process trees.
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -Mode Student -CheckOnly
.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch.ps1 -Mode Solution
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Student', 'Solution')][string]$Mode,
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 5173,
    [switch]$CheckOnly,
    [switch]$SkipInstall
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

function Find-FreePort([int]$Requested, [int]$Exclude = 0) {
    for ($candidate = $Requested; $candidate -le 65535; $candidate++) {
        if ($candidate -eq $Exclude) { continue }
        $listener = New-Object Net.Sockets.TcpListener ([Net.IPAddress]::Loopback), $candidate
        try {
            $listener.Server.ExclusiveAddressUse = $true
            $listener.Start()
            return $candidate
        } catch [Net.Sockets.SocketException] {
            continue
        } finally {
            $listener.Stop()
        }
    }
    throw 'No available localhost port at or above the requested port.'
}

function Quote-Argument([string]$Value) {
    if ($Value.Contains('"') -or $Value.EndsWith('\')) {
        throw 'Unsupported quote or trailing separator in process argument.'
    }
    return '"' + $Value + '"'
}

function Start-DirectProcess([string]$Executable, [string[]]$Arguments, [string]$Directory) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.Arguments = ($Arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $info.WorkingDirectory = $Directory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    return [Diagnostics.Process]::Start($info)
}

function Remember-Children([Diagnostics.Process]$Parent, [hashtable]$Tracked) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($Parent.Id)" `
        -ErrorAction SilentlyContinue)
    foreach ($child in $children) {
        if (-not $Tracked.ContainsKey([int]$child.ProcessId)) {
            $process = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($null -ne $process) {
                $Tracked[[int]$child.ProcessId] = $process
                Remember-Children $process $Tracked
            }
        }
    }
}

function Stop-Tree([Diagnostics.Process]$Process) {
    try {
        if (-not $Process.HasExited) {
            & "$env:SystemRoot\System32\taskkill.exe" /PID $Process.Id /T /F 2>$null | Out-Null
        }
    } catch {
        Write-Warning "Could not stop process $($Process.Id); inspect it before stopping manually."
    }
}

foreach ($relative in @('backend\pyproject.toml', 'backend\uv.lock', 'backend\app\main.py',
        'frontend\package.json', 'frontend\vite.config.ts', 'frontend\src\api\index.ts')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $relative) -PathType Leaf)) {
        throw "Missing workshop file: $relative"
    }
}
if ($Mode -eq 'Solution' -and -not (Test-Path -LiteralPath `
        (Join-Path $Root 'instructor\solution.py') -PathType Leaf)) {
    throw 'Solution mode requires instructor/solution.py physically present in this checkout.'
}
$Uv = (Get-Command uv -CommandType Application -ErrorAction Stop).Source
$Npm = (Get-Command npm.cmd -CommandType Application -ErrorAction Stop).Source
$Node = (Get-Command node -CommandType Application -ErrorAction Stop).Source
$Python = & $Uv python find 3.12 --no-python-downloads
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with uv python install 3.12 before class.' }
$Python = [string](@($Python)[-1])
& $Python -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
if ($LASTEXITCODE -ne 0) { throw 'The selected interpreter is not Python 3.12.' }
$NodeVersion = [version]((& $Node --version).Trim().TrimStart('v'))
if (-not (($NodeVersion.Major -eq 20 -and $NodeVersion -ge [version]'20.19.0') -or
        ($NodeVersion.Major -ge 22 -and $NodeVersion -ge [version]'22.12.0'))) {
    throw 'Vite requires Node 20.19+ (20.x) or Node 22.12+.'
}
& $Npm --version
if ($LASTEXITCODE -ne 0) { throw 'npm preflight failed.' }
$BackendPort = Find-FreePort $BackendPort
$FrontendPort = Find-FreePort $FrontendPort $BackendPort
$ApiUrl = "http://127.0.0.1:$BackendPort"
$UiUrl = "http://127.0.0.1:$FrontendPort"
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$Vite = Join-Path $Frontend 'node_modules\vite\bin\vite.js'
$DataBase = Join-Path $Root '.workshop-data\app'
Write-Output "Mode: $Mode; app data: $(Join-Path $DataBase $Mode.ToLowerInvariant())"
Write-Output "Backend: $ApiUrl; frontend: $UiUrl"
Write-Output 'Ports are checked, not reserved; a startup race fails rather than changing the proxy.'
$ApiEntry = Get-Content -LiteralPath (Join-Path $Frontend 'src\api\index.ts') -Raw
$HasLiveFlag = $ApiEntry.Contains('VITE_WORKSHOP_API_MODE')
if (-not $HasLiveFlag -and $ApiEntry.Contains('= mockClient')) {
    Write-Warning 'Frontend API is hardwired to mocks. Backend proxy is configured, but live UI wiring is pending.'
}
if ($CheckOnly) {
    Write-Output "PASS preflight: uv, npm, Node, Python 3.12, manifests, mode and available ports. No installs or servers."
    return
}
if (-not $SkipInstall) {
    & $Uv sync --project $Backend --python 3.12 --locked --no-python-downloads
    if ($LASTEXITCODE -ne 0) { throw 'Locked backend dependency installation failed.' }
    if (Test-Path -LiteralPath (Join-Path $Frontend 'package-lock.json') -PathType Leaf) {
        & $Npm --prefix $Frontend ci
    } else {
        & $Npm --prefix $Frontend install
    }
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
}
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf) -or
        -not (Test-Path -LiteralPath $Vite -PathType Leaf)) {
    throw 'Dependencies are missing. Run again without -SkipInstall.'
}
& $VenvPython -c 'import sys, uvicorn; assert sys.version_info[:2] == (3, 12)'
if ($LASTEXITCODE -ne 0) { throw 'Backend venv is incompatible; rerun without -SkipInstall.' }

$Saved = @{}
$Managed = @('WORKSHOP_MODE', 'WORKSHOP_DATA_DIR', 'FRONTEND_ORIGIN', 'WORKSHOP_API_URL',
    'VITE_WORKSHOP_API_MODE', 'OPENAI_API_KEY')
foreach ($name in $Managed) { $Saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$Processes = @()
$Children = @{}
try {
    try {
        $env:WORKSHOP_MODE = $Mode.ToLowerInvariant()
        $env:WORKSHOP_DATA_DIR = $DataBase
        $env:FRONTEND_ORIGIN = $UiUrl
        $env:WORKSHOP_API_URL = $ApiUrl
        if ($HasLiveFlag) { $env:VITE_WORKSHOP_API_MODE = 'live' }
        $backendArgs = @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1',
            '--port', [string]$BackendPort)
        $EnvFile = Join-Path $Backend '.env'
        if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
            $backendArgs += @('--env-file', $EnvFile)
        }
        $Processes += Start-DirectProcess $VenvPython $backendArgs $Root
        [Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $null, 'Process')
        $Processes += Start-DirectProcess $Node @($Vite, '--host', '127.0.0.1', '--port',
            [string]$FrontendPort, '--strictPort') $Frontend
    } finally {
        foreach ($name in $Managed) {
            [Environment]::SetEnvironmentVariable($name, $Saved[$name], 'Process')
        }
    }
    Write-Output "Backend PID: $($Processes[0].Id); frontend PID: $($Processes[1].Id). Ctrl+C stops both trees."
    Write-Output "Emergency shutdown: taskkill /PID $($Processes[0].Id) /T /F; taskkill /PID $($Processes[1].Id) /T /F"
    while ($true) {
        foreach ($process in $Processes) { Remember-Children $process $Children }
        if ($Processes[0].WaitForExit(250) -or $Processes[1].HasExited) {
            throw 'A workshop process exited. Both process trees will be stopped; inspect startup output.'
        }
    }
} finally {
    foreach ($process in $Processes) { Stop-Tree $process }
    foreach ($process in $Children.Values) { Stop-Tree $process }
}