<#
.SYNOPSIS
    한일 TimeGuard 관리 서버를 설치합니다.

.DESCRIPTION
    사내 PC 한 대에 설치해 두면, 직원 PC 들이 이 서버에서 시간표를 받아 갑니다.
    이 스크립트는 반드시 관리자 권한 PowerShell 에서 실행해야 합니다.

    설치한 PC 는 항상 켜 두어야 합니다.
    (꺼져 있어도 직원 PC 는 마지막으로 받은 시간표를 그대로 적용합니다.)

.PARAMETER Port
    웹 화면과 클라이언트가 접속할 포트. 기본 8080.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install-server.ps1
    powershell -ExecutionPolicy Bypass -File .\install-server.ps1 -Port 9000
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "$env:ProgramFiles\HanilTimeGuardServer",
    [int]$Port = 8080
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'HanilTimeGuardServer'
$DataPath    = "$env:ProgramData\HanilTimeGuardServer"

function Write-Step { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Message) Write-Host "    $Message" -ForegroundColor Green }
function Write-Warn2{ param([string]$Message) Write-Host "    $Message" -ForegroundColor Yellow }

# --- 관리자 권한 확인 ---
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '이 스크립트는 관리자 권한으로 실행해야 합니다.' -ForegroundColor Red
    Write-Host 'PowerShell 을 마우스 오른쪽 클릭 후 [관리자 권한으로 실행] 을 선택해 주세요.' -ForegroundColor Red
    exit 1
}

$source = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path (Join-Path $source 'TimeGuard.Server.exe'))) {
    Write-Host "TimeGuard.Server.exe 를 찾을 수 없습니다: $source" -ForegroundColor Red
    exit 1
}

# --- 기존 서비스 중지 ---
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Step '기존 서버를 중지합니다'
    if ($existing.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $existing.WaitForStatus('Stopped', '00:00:30')
    }
    Write-Ok '중지했습니다.'
}

# --- 파일 복사 ---
Write-Step "프로그램 파일을 복사합니다: $InstallPath"
New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $InstallPath -Recurse -Force
Write-Ok '복사를 마쳤습니다.'

# --- 포트 설정 ---
Write-Step "접속 포트를 설정합니다: $Port"
$settingsPath = Join-Path $InstallPath 'appsettings.json'
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
$settings.Kestrel.Endpoints.Http.Url = "http://0.0.0.0:$Port"
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8
Write-Ok '설정했습니다.'

# --- 자료 폴더 권한 ---
# 데이터베이스에 관리자 비밀번호 해시와 장비 토큰이 들어 있으므로 일반 사용자는 접근할 수 없게 한다
Write-Step "자료 폴더 권한을 설정합니다: $DataPath"
New-Item -ItemType Directory -Path $DataPath -Force | Out-Null

$acl = Get-Acl $DataPath
$acl.SetAccessRuleProtection($true, $false)

foreach ($account in @('SYSTEM', 'Administrators')) {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $account, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
}

Set-Acl -Path $DataPath -AclObject $acl
Write-Ok '관리자만 접근할 수 있도록 설정했습니다.'

# --- 서비스 등록 ---
$binaryPath = Join-Path $InstallPath 'TimeGuard.Server.exe'

if ($existing) {
    Write-Step '서비스 설정을 갱신합니다'
    & sc.exe config $ServiceName binPath= "`"$binaryPath`"" start= auto | Out-Null
} else {
    Write-Step '서비스를 등록합니다'
    & sc.exe create $ServiceName binPath= "`"$binaryPath`"" start= auto DisplayName= "한일 TimeGuard 관리 서버" | Out-Null
}

& sc.exe description $ServiceName "직원 PC 의 사용 시간표를 관리하고 연장 요청을 받습니다." | Out-Null
& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/10000 | Out-Null
Write-Ok '등록했습니다.'

# --- 방화벽 ---
Write-Step "방화벽에서 포트 $Port 를 엽니다"
$ruleName = "한일 TimeGuard 관리 서버 ($Port)"
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

New-NetFirewallRule -DisplayName $ruleName `
                    -Direction Inbound -Protocol TCP -LocalPort $Port `
                    -Action Allow -Profile Domain,Private | Out-Null
Write-Ok '열었습니다. (사내망에서만 접속할 수 있습니다)'

# --- 시작 ---
Write-Step '서버를 시작합니다'
Start-Service -Name $ServiceName
Start-Sleep -Seconds 4

$service = Get-Service -Name $ServiceName
if ($service.Status -ne 'Running') {
    Write-Warn2 "서버 상태: $($service.Status)"
    Write-Warn2 '이벤트 뷰어의 응용 프로그램 로그를 확인해 주세요.'
    exit 1
}

Write-Ok '서버가 실행 중입니다.'

# --- 접속 주소 안내 ---
$address = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1).IPAddress

$notePath = Join-Path $DataPath '최초설정정보.txt'

Write-Host ''
Write-Host '설치가 끝났습니다.' -ForegroundColor Green
Write-Host ''
Write-Host '  관리 화면 주소' -ForegroundColor White
Write-Host "    이 PC 에서   : http://localhost:$Port"
if ($address) {
    Write-Host "    다른 PC 에서 : http://${address}:$Port"
}
Write-Host ''

if (Test-Path $notePath) {
    Write-Host '  최초 로그인 정보' -ForegroundColor White
    Get-Content $notePath | ForEach-Object { Write-Host "    $_" }
    Write-Host ''
    Write-Warn2 "로그인 후 비밀번호를 바꾸고 아래 파일을 삭제하십시오:"
    Write-Warn2 "  $notePath"
} else {
    Write-Host "  최초 로그인 정보: $notePath" -ForegroundColor White
}

Write-Host ''
Write-Host '  다음 순서' -ForegroundColor White
Write-Host '    1) 웹 브라우저로 위 주소에 접속해 admin 으로 로그인'
Write-Host '    2) [설정] 에서 비밀번호 변경'
Write-Host '    3) [기본 시간표] 에서 허용 시간대 지정'
Write-Host '    4) [설정] 화면의 등록 키를 확인해 직원 PC 에 클라이언트 설치'
Write-Host ''
