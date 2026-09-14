<#
.SYNOPSIS
    한일 TimeGuard 클라이언트를 설치합니다.

.DESCRIPTION
    관리자 권한 PowerShell 에서 실행해야 합니다.

    관리 서버를 쓰는 경우 -Server 와 -Key 를 주면
    설치부터 서버 등록까지 한 번에 끝납니다.
    (두 값은 서버의 [설정] 화면에 그대로 나와 있습니다.)

.PARAMETER Server
    관리 서버 주소. 예: http://192.168.0.10:8080

.PARAMETER Key
    서버의 [설정] 화면에 있는 클라이언트 등록 키.

.EXAMPLE
    # 서버에 붙여서 쓰는 경우 (권장)
    .\install.ps1 -Server http://192.168.0.10:8080 -Key ABCDE-FGHIJ-KLMNO-PQRST

.EXAMPLE
    # 이 PC 하나만 단독으로 쓰는 경우
    .\install.ps1
#>

[CmdletBinding()]
param(
    [string]$Server,
    [string]$Key,
    [string]$InstallPath = "$env:ProgramFiles\HanilTimeGuard"
)

$ErrorActionPreference = 'Stop'
$ServiceName = 'HanilTimeGuard'
$DataPath    = "$env:ProgramData\HanilTimeGuard"

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

if (-not (Test-Path (Join-Path $source 'TimeGuard.Service.exe'))) {
    Write-Host "TimeGuard.Service.exe 를 찾을 수 없습니다: $source" -ForegroundColor Red
    Write-Host '배포 폴더 안에서 스크립트를 실행해 주세요.' -ForegroundColor Red
    exit 1
}

# --- 기존 서비스 중지 ---
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Step '기존 서비스를 중지합니다'
    if ($existing.Status -ne 'Stopped') {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        $existing.WaitForStatus('Stopped', '00:00:30')
    }
    Write-Ok '중지했습니다.'
}

# 파일이 잠겨 있지 않도록 알림 프로그램도 종료한다
Get-Process -Name 'TimeGuard.Agent' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# --- 파일 복사 ---
Write-Step "프로그램 파일을 복사합니다: $InstallPath"
New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $InstallPath -Recurse -Force
Write-Ok '복사를 마쳤습니다.'

# --- 설정 폴더와 권한 ---
Write-Step "설정 폴더 권한을 설정합니다: $DataPath"
New-Item -ItemType Directory -Path $DataPath -Force | Out-Null

# 일반 사용자는 읽기만 가능하게 해서 설정 파일을 직접 고치지 못하게 한다
$acl = Get-Acl $DataPath
$acl.SetAccessRuleProtection($true, $false)   # 상속 제거

$rules = @(
    New-Object Security.AccessControl.FileSystemAccessRule(
        'SYSTEM', 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'),
    New-Object Security.AccessControl.FileSystemAccessRule(
        'Administrators', 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'),
    New-Object Security.AccessControl.FileSystemAccessRule(
        'Users', 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
)

foreach ($rule in $rules) { $acl.AddAccessRule($rule) }
Set-Acl -Path $DataPath -AclObject $acl
Write-Ok '일반 사용자는 읽기만 가능하도록 설정했습니다.'

# --- 서비스 등록 ---
$binaryPath = Join-Path $InstallPath 'TimeGuard.Service.exe'

if ($existing) {
    Write-Step '서비스 설정을 갱신합니다'
    & sc.exe config $ServiceName binPath= "`"$binaryPath`"" start= auto | Out-Null
} else {
    Write-Step '서비스를 등록합니다'
    & sc.exe create $ServiceName binPath= "`"$binaryPath`"" start= auto DisplayName= "한일 TimeGuard" | Out-Null
}

& sc.exe description $ServiceName "허용된 시간대를 벗어나면 안내 후 설정된 조치를 수행합니다." | Out-Null

# 서비스가 죽으면 자동으로 다시 시작하게 한다
& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/10000 | Out-Null
Write-Ok '등록했습니다.'

# --- 알림 프로그램 자동 실행 등록 ---
# 서비스도 직접 띄우지만, 로그온 직후 바로 뜨도록 시작 프로그램에도 넣어 둔다
Write-Step '알림 프로그램을 시작 프로그램에 등록합니다'
$runKey   = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
$agentExe = Join-Path $InstallPath 'TimeGuard.Agent.exe'
New-ItemProperty -Path $runKey -Name 'HanilTimeGuardAgent' -Value "`"$agentExe`"" -PropertyType String -Force | Out-Null
Write-Ok '등록했습니다.'

# --- 서비스 시작 ---
Write-Step '서비스를 시작합니다'
Start-Service -Name $ServiceName
Start-Sleep -Seconds 2

$service = Get-Service -Name $ServiceName
if ($service.Status -eq 'Running') {
    Write-Ok '서비스가 실행 중입니다.'
} else {
    Write-Warn2 "서비스 상태: $($service.Status)"
    Write-Warn2 "이벤트 뷰어의 응용 프로그램 로그를 확인해 주세요."
}

# --- 관리 서버에 등록 ---
$adminExe = Join-Path $InstallPath 'TimeGuard.Admin.exe'

if ($Server -and $Key) {
    Write-Step "관리 서버에 등록합니다: $Server"

    & $adminExe enroll --server $Server --key $Key
    $enrolled = ($LASTEXITCODE -eq 0)

    if ($enrolled) {
        # 등록 직후 서비스를 다시 띄워야 서버 시간표를 바로 받아 온다
        Write-Step '서비스를 다시 시작해 서버 시간표를 받아옵니다'
        Restart-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 3
        Write-Ok '등록을 마쳤습니다.'
    } else {
        Write-Warn2 '서버 등록에 실패했습니다. 설치 자체는 끝났습니다.'
        Write-Warn2 '서버 주소와 등록 키를 확인한 뒤 아래를 다시 실행해 주세요:'
        Write-Warn2 "  `"$adminExe`" enroll --server $Server --key $Key"
    }
} elseif ($Server -or $Key) {
    Write-Warn2 '-Server 와 -Key 는 둘 다 필요합니다. 서버 등록을 건너뜁니다.'
    $enrolled = $false
} else {
    $enrolled = $false
}

# --- 안내 ---
Write-Host ''
Write-Host '설치가 끝났습니다.' -ForegroundColor Green
Write-Host ''

if ($enrolled) {
    Write-Host '이 PC 는 관리 서버가 관리합니다.' -ForegroundColor Green
    Write-Host '  · 서버의 [PC 목록] 에 이 PC 가 나타납니다.'
    Write-Host '  · 시간표 변경과 연장 승인은 서버 화면에서 합니다.'
    Write-Host '  · 더 하실 일이 없습니다.'
    Write-Host ''
    Write-Host '  이 PC 상태 확인:' -ForegroundColor White
    Write-Host "    `"$adminExe`" status"
} else {
    Write-Host '중요: 지금은 감시가 꺼져 있어 아무도 제한받지 않습니다.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  관리 서버를 쓰시려면' -ForegroundColor White
    Write-Host "    `"$adminExe`" enroll --server http://서버주소:8080 --key 등록키"
    Write-Host '    net stop HanilTimeGuard && net start HanilTimeGuard'
    Write-Host ''
    Write-Host '  이 PC 하나만 단독으로 쓰시려면' -ForegroundColor White
    Write-Host "    `"$adminExe`" 를 실행해 아래 순서로 설정합니다"
    Write-Host '      [10] 관리자 비밀번호 변경 → [2] 허용 시간대 → [4] 조치 → [3] 감시 켜기'
}

Write-Host ''
Write-Host "설정 파일: $DataPath\config.json"
Write-Host "기록 파일: $DataPath\timeguard.log"
Write-Host ''
