<#
.SYNOPSIS
    한일 TimeGuard 관리 서버를 제거합니다.

.PARAMETER KeepData
    설정과 기록(데이터베이스)을 남겨 둡니다.
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "$env:ProgramFiles\HanilTimeGuardServer",
    [int]$Port = 8080,
    [switch]$KeepData
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'HanilTimeGuardServer'
$DataPath    = "$env:ProgramData\HanilTimeGuardServer"

function Write-Step { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '이 스크립트는 관리자 권한으로 실행해야 합니다.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '주의: 서버를 제거해도 직원 PC 는 마지막으로 받은 시간표를 계속 적용합니다.' -ForegroundColor Yellow
Write-Host '      직원 PC 의 제한을 풀려면 각 PC 에서 아래를 실행해야 합니다.' -ForegroundColor Yellow
Write-Host '        TimeGuard.Admin.exe unenroll' -ForegroundColor Yellow
Write-Host ''

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Step '서버를 중지하고 등록을 해제합니다'
    if ($service.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $service.WaitForStatus('Stopped', '00:00:30')
    }
    & sc.exe delete $ServiceName | Out-Null
}

Write-Step '방화벽 규칙을 제거합니다'
Remove-NetFirewallRule -DisplayName "한일 TimeGuard 관리 서버 ($Port)" -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

if (Test-Path $InstallPath) {
    Write-Step "프로그램 파일을 삭제합니다: $InstallPath"
    Remove-Item -Path $InstallPath -Recurse -Force -ErrorAction SilentlyContinue
}

if ($KeepData) {
    Write-Host "자료는 그대로 두었습니다: $DataPath" -ForegroundColor Yellow
} elseif (Test-Path $DataPath) {
    Write-Step "자료를 삭제합니다: $DataPath"
    Remove-Item -Path $DataPath -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host '제거가 끝났습니다.' -ForegroundColor Green
