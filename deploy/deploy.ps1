<#
.SYNOPSIS
    One-click deploy 2Flowers (万物生花) to remote Linux server
.DESCRIPTION
    上传 backend/ 和 front/ 到远程，安装环境，构建前端，配置 nginx，启动服务。
.EXAMPLE
    .\deploy.ps1 -ServerIp 39.108.90.226 -User root -Password "你的密码"
.EXAMPLE
    .\deploy.ps1 -ServerIp 39.108.90.226 -User root -Password "你的密码" -SkipSetup
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ServerIp,

    [string]$User = "root",

    [Parameter(Mandatory=$true)]
    [string]$Password,

    [string]$RemoteDir = "/opt/2flowers",

    [switch]$SkipSetup,

    [switch]$SkipUpload
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LocalBackend = Join-Path $ProjectRoot "backend"
$LocalFrontend = Join-Path $ProjectRoot "front"
$LocalEnvFile = Join-Path $LocalBackend ".env"
$DeployDir = $PSScriptRoot

$script:PlinkPath = 'C:\Program Files\PuTTY\plink.exe'
$script:PscpPath = 'C:\Program Files\PuTTY\pscp.exe'

# Auto-accept and cache server host key on first connect (one-time trust)
function Ensure-HostKeyCached {
    Write-Host "  Caching host key for $ServerIp..."
    $echo = & $script:PlinkPath -ssh -P 22 -l $User -pw $Password $ServerIp "echo ok" 2>&1
    if ($LASTEXITCODE -ne 0 -and ($echo -match 'Access denied' -or $echo -match 'FATAL ERROR')) {
        # host key already cached but auth failed -> let later steps report the real error
        return
    }
    # Feed "y" to accept new host key
    $result = 'y' | & $script:PlinkPath -ssh -P 22 -l $User -pw $Password $ServerIp "echo ok" 2>&1
    if ($LASTEXITCODE -ne 0 -and ($result -notmatch 'Access denied')) {
        Write-Host ($result | Out-String)
        throw "Cannot connect to $ServerIp. Check IP / network / password."
    }
}

function Write-Step($msg) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}
function Write-OK($msg)   { Write-Host "[OK]  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[X]  $msg" -ForegroundColor Red }

function Invoke-RemoteCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$Description
    )
    Write-Host "  $Description..."
    & $script:PlinkPath -ssh -batch -P 22 -l $User -pw $Password $ServerIp $Command
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) { throw "$Description failed, exit code: $ExitCode" }
}

function Invoke-ScpUpload {
    param(
        [Parameter(Mandatory = $true)][string]$LocalPath,
        [Parameter(Mandatory = $true)][string]$RemotePath
    )
    & $script:PscpPath -batch -P 22 -l $User -pw $Password $LocalPath "${User}@${ServerIp}:${RemotePath}"
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) { throw "SCP upload failed, exit code: $ExitCode" }
}

try {
    # ---------- Step 1: Check local tools ----------
    Write-Step "Step 1: Check local SSH tools"
    if (-not (Test-Path $script:PlinkPath)) { throw "plink not found at $script:PlinkPath. Install PuTTY first." }
    if (-not (Test-Path $script:PscpPath)) { throw "pscp not found at $script:PscpPath. Install PuTTY first." }
    Write-OK "plink -> $script:PlinkPath"
    Write-OK "pscp  -> $script:PscpPath"

    Ensure-HostKeyCached
    Write-OK "Host key cached for $ServerIp"

    # ---------- Step 2: Upload project code ----------
    if (-not $SkipUpload) {
        Write-Step "Step 2: Upload project code to $RemoteDir"

        Invoke-RemoteCommand -Description "Create remote directories" -Command "mkdir -p $RemoteDir/backend $RemoteDir/front $RemoteDir/deploy"

        $tempTar = Join-Path $env:TEMP "2flowers-deploy.tar.gz"
        if (Test-Path $tempTar) { Remove-Item $tempTar -Force }

        Write-Host "  Packing project (exclude cache/deps/env)..."
        Push-Location $ProjectRoot
        try {
            tar -czf $tempTar `
                --exclude='backend/__pycache__' `
                --exclude='backend/.venv' `
                --exclude='backend/.env' `
                --exclude='backend/*.db' `
                --exclude='backend/uploads/*' `
                --exclude='backend/logs/*' `
                --exclude='front/node_modules' `
                --exclude='front/dist' `
                --exclude='front/*.log' `
                --exclude='backend/*.log' `
                --exclude='*.pyc' `
                --exclude='__pycache__' `
                backend front deploy 2>&1 | Out-Null
        } finally {
            Pop-Location
        }

        $tarSize = [math]::Round((Get-Item $tempTar).Length / 1MB, 2)
        Write-OK "Packed ($tarSize MB): $tempTar"

        Write-Host "  Uploading to server..."
        Invoke-ScpUpload -LocalPath $tempTar -RemotePath "/tmp/2flowers-deploy.tar.gz"
        Write-OK "Upload done"

        Write-Host "  Remote extracting..."
        Invoke-RemoteCommand -Description "Extract project on server" -Command "rm -rf $RemoteDir/backend $RemoteDir/front $RemoteDir/deploy; mkdir -p $RemoteDir; cd $RemoteDir; tar -xzf /tmp/2flowers-deploy.tar.gz; rm -f /tmp/2flowers-deploy.tar.gz; ls -la"
        Remove-Item $tempTar -Force -ErrorAction SilentlyContinue
        Write-OK "Code deployed"
    } else {
        Write-Warn "Skip code upload"
    }

    # ---------- Step 2.5: Upload .env separately (contains API keys) ----------
    if (Test-Path $LocalEnvFile) {
        Write-Step "Step 2.5: Upload backend/.env (API keys)"
        Invoke-ScpUpload -LocalPath $LocalEnvFile -RemotePath "$RemoteDir/backend/.env"
        Write-OK ".env uploaded"
    } else {
        Write-Warn "backend/.env not found locally, skip. You must create it on server manually."
    }

    # Upload helper scripts
    Write-Host "  Upload helper scripts..."
    Invoke-ScpUpload -LocalPath (Join-Path $DeployDir "server-setup.sh") -RemotePath "/tmp/server-setup.sh"
    Invoke-ScpUpload -LocalPath (Join-Path $DeployDir "server-start.sh") -RemotePath "/tmp/server-start.sh"

    # ---------- Step 3: Remote environment setup ----------
    if (-not $SkipSetup) {
        Write-Step "Step 3: Remote environment setup (first time 3-5 min)"
        Write-Warn "Installing Python3.11 / Node.js 22 / nginx, please wait..."
        Invoke-RemoteCommand -Description "Running remote environment setup" -Command "sed -i 's/\r$//' /tmp/server-setup.sh; chmod +x /tmp/server-setup.sh; /tmp/server-setup.sh"
        Write-OK "Environment setup done"
    } else {
        Write-Warn "Skip environment setup"
    }

    # ---------- Step 4: Start services ----------
    Write-Step "Step 4: Start services"
    Invoke-RemoteCommand -Description "Starting remote services" -Command "sed -i 's/\r$//' /tmp/server-start.sh; chmod +x /tmp/server-start.sh; /tmp/server-start.sh"
    Write-OK "Services started"

    # ---------- Done ----------
    Write-Step "Deploy complete!"
    Write-Host ""
    Write-Host "  Frontend: http://${ServerIp}" -ForegroundColor Green
    Write-Host "  Backend:  http://${ServerIp}:8000/docs" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Backend logs:" -ForegroundColor Yellow
    Write-Host "    ssh ${User}@${ServerIp} 'journalctl -u 2flowers-backend -f'"
    Write-Host ""
    Write-Host "  Nginx logs:" -ForegroundColor Yellow
    Write-Host "    ssh ${User}@${ServerIp} 'tail -f /var/log/nginx/error.log'"
    Write-Host ""
    Write-Warn "Please change server root password immediately!"

    exit 0
}
catch {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  DEPLOY FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    exit 1
}
