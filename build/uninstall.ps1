<#
.SYNOPSIS
    한일 TimeGuard 를 제거합니다.

.PARAMETER KeepSettings
    설정과 기록 파일을 남겨 둡니다.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "$env:ProgramFiles\HanilTimeGuard",
    [switch]$KeepSettings
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'HanilTimeGuard'
$DataPath    = "$env:ProgramData\HanilTimeGuard"

function Write-Step { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '이 스크립트는 관리자 권한으로 실행해야 합니다.' -ForegroundColor Red
    exit 1
}

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    # 설치할 때 걸어 둔 보호를 먼저 되돌린다. 그러지 않으면 중지할 수 없다.
    Write-Step '서비스 보호를 해제합니다'
    & sc.exe sdset $ServiceName 'D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCLCSWRPWPDTLOCRRC;;;BA)(A;;CCLCSWLOCRRC;;;IU)(A;;CCLCSWLOCRRC;;;SU)' | Out-Null

    Write-Step '서비스를 중지하고 등록을 해제합니다'
    if ($service.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $service.WaitForStatus('Stopped', '00:00:30')
    }
    & sc.exe delete $ServiceName | Out-Null
}

# --- 잠긴 계정 풀기 ---
# 계정 잠금 조치를 쓰던 중에 제거하면 직원이 로그인하지 못하게 된다.
$lockedPath = Join-Path $DataPath 'locked-accounts.json'
if (Test-Path $lockedPath) {
    Write-Step '잠겨 있던 계정을 풀어 줍니다'
    try {
        $locked = Get-Content $lockedPath -Raw | ConvertFrom-Json
        foreach ($entry in @($locked)) {
            if ($entry.userName) {
                & net user $entry.userName /active:yes 2>&1 | Out-Null
                Write-Host "    $($entry.userName) 계정을 풀었습니다." -ForegroundColor Green
            }
        }
    } catch {
        Write-Host '    잠긴 계정 정보를 읽지 못했습니다.' -ForegroundColor Yellow
        Write-Host '    직접 풀려면: net user <계정이름> /active:yes' -ForegroundColor Yellow
    }
}

Write-Step '알림 프로그램을 종료합니다'
Get-Process -Name 'TimeGuard.Agent' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Step '시작 프로그램 등록을 해제합니다'
Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' `
                    -Name 'HanilTimeGuardAgent' -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

if (Test-Path $InstallPath) {
    Write-Step "프로그램 파일을 삭제합니다: $InstallPath"

    # 설치할 때 걸어 둔 삭제 금지를 먼저 되돌린다.
    try {
        $acl = Get-Acl $InstallPath
        $acl.SetAccessRuleProtection($false, $true)
        $denyRules = @($acl.Access | Where-Object { $_.AccessControlType -eq 'Deny' })
        foreach ($rule in $denyRules) { $acl.RemoveAccessRule($rule) | Out-Null }
        Set-Acl -Path $InstallPath -AclObject $acl
    } catch {
        Write-Host '    폴더 권한을 되돌리지 못했습니다. 삭제가 실패할 수 있습니다.' -ForegroundColor Yellow
    }

    Remove-Item -Path $InstallPath -Recurse -Force -ErrorAction SilentlyContinue
}

if ($KeepSettings) {
    Write-Host "설정과 기록은 그대로 두었습니다: $DataPath" -ForegroundColor Yellow
} elseif (Test-Path $DataPath) {
    Write-Step "설정과 기록을 삭제합니다: $DataPath"
    Remove-Item -Path $DataPath -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host '제거가 끝났습니다.' -ForegroundColor Green
