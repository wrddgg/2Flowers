param(
    [switch]$NoRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPath = Join-Path $Root ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$PipExe = Join-Path $VenvPath "Scripts\pip.exe"
$HostAddress = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$PortNumber = if ($env:PORT) { $env:PORT } else { "8000" }

Write-Host "==> 准备虚拟环境"
if (-not (Test-Path $PythonExe)) {
    python -m venv $VenvPath
}

Write-Host "==> 安装依赖"
& $PythonExe -m pip install --upgrade pip
& $PipExe install -r (Join-Path $Root "requirements.txt")

if ($NoRun) {
    Write-Host "==> 依赖安装完成，已跳过启动"
    exit 0
}

Write-Host "==> 启动服务 http://$HostAddress`:$PortNumber"
& $PythonExe -m uvicorn app.main:app --host $HostAddress --port $PortNumber --reload --app-dir $Root
