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
    Write-Step '서비스를 중지하고 등록을 해제합니다'
    if ($service.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $service.WaitForStatus('Stopped', '00:00:30')
    }
    & sc.exe delete $ServiceName | Out-Null
}

Write-Step '알림 프로그램을 종료합니다'
Get-Process -Name 'TimeGuard.Agent' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Step '시작 프로그램 등록을 해제합니다'
Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' `
                    -Name 'HanilTimeGuardAgent' -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

if (Test-Path $InstallPath) {
    Write-Step "프로그램 파일을 삭제합니다: $InstallPath"
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
