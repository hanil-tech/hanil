<#
.SYNOPSIS
    한일 TimeGuard 클라이언트를 설치합니다.

.DESCRIPTION
    관리자 권한 PowerShell 에서 실행해야 합니다.

    관리 서버를 쓰는 경우 -Server 와 -Key 를 주면
    설치부터 서버 등록까지 한 번에 끝납니다.
    (두 값은 서버의 [설정] 화면에 그대로 나와 있습니다.)

.PARAMETER Key
    서버의 [설정] 화면에 있는 클라이언트 등록 키.
    이것만 주면 서버는 사내망에서 자동으로 찾습니다.

.PARAMETER Server
    관리 서버 주소. 적지 않으면 사내망에서 찾습니다.
    예: https://192.168.0.10:8443

.EXAMPLE
    # 가장 간단한 방법 - 서버는 알아서 찾습니다
    .\install.ps1 -Key ABCDE-FGHIJ-KLMNO-PQRST

.EXAMPLE
    # 서버 주소를 직접 적는 경우
    .\install.ps1 -Server https://192.168.0.10:8443 -Key ABCDE-FGHIJ-KLMNO-PQRST

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

# --- 프로그램 폴더 보호 ---
# 일반 사용자가 실행 파일을 지우거나 바꿔치기하지 못하게 한다.
Write-Step '프로그램 폴더를 보호합니다'
$programAcl = Get-Acl $InstallPath
$programAcl.SetAccessRuleProtection($true, $false)

foreach ($account in @('SYSTEM', 'Administrators')) {
    $programAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $account, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
}

# 일반 사용자는 실행만 할 수 있고 지우거나 고칠 수 없다
$programAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
    'Users', 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))

$programAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
    'Users', 'Delete,DeleteSubdirectoriesAndFiles,Write', 'ContainerInherit,ObjectInherit', 'None', 'Deny')))

Set-Acl -Path $InstallPath -AclObject $programAcl
Write-Ok '일반 사용자는 지우거나 고칠 수 없습니다.'

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

# 서비스가 스스로 멈춘 경우에도 복구 동작을 적용한다(기본값은 비정상 종료만 해당)
& sc.exe failureflag $ServiceName 1 | Out-Null
Write-Ok '등록했습니다.'

# --- 서비스 보호 ---
# 일반 사용자는 물론 관리자도 실수로 멈추지 못하게 권한을 좁힌다.
# SYSTEM 은 그대로 모든 권한을 가지므로 서비스 자신과 제거 스크립트는 문제없이 동작한다.
#
#   D:  권한 목록
#   A;;CCLCSWRPWPDTLOCRRC;;;SY    SYSTEM       : 전체 권한
#   A;;CCLCSWRPDTLOCRRC;;;BA     관리자 그룹   : 조회와 설정은 되지만 중지(WP)는 뺐다
#   A;;CCLCSWLOCRRC;;;IU         로그인 사용자 : 조회만
#   A;;CCLCSWLOCRRC;;;SU         서비스 계정   : 조회만
Write-Step '서비스를 함부로 멈출 수 없게 보호합니다'
$sddl = 'D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCLCSWRPDTLOCRRC;;;BA)(A;;CCLCSWLOCRRC;;;IU)(A;;CCLCSWLOCRRC;;;SU)S:(AU;FA;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;WD)'
& sc.exe sdset $ServiceName $sddl | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Ok '설정했습니다. (제거할 때는 uninstall.ps1 이 알아서 되돌립니다)'
} else {
    Write-Warn2 '서비스 보호 설정에 실패했습니다. 설치는 계속됩니다.'
}

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

if ($Key) {
    if ($Server) {
        Write-Step "관리 서버에 등록합니다: $Server"
        & $adminExe enroll --server $Server --key $Key --yes
    } else {
        Write-Step '사내망에서 관리 서버를 찾아 등록합니다'
        & $adminExe enroll --key $Key --yes
    }

    $enrolled = ($LASTEXITCODE -eq 0)

    if ($enrolled) {
        # 등록 직후 서비스를 다시 띄워야 서버 시간표를 바로 받아 온다
        Write-Step '서비스를 다시 시작해 서버 시간표를 받아옵니다'
        Restart-Service -Name $ServiceName -Force
        Start-Sleep -Seconds 3
        Write-Ok '등록을 마쳤습니다.'
    } else {
        Write-Warn2 '서버 등록에 실패했습니다. 설치 자체는 끝났습니다.'
        Write-Warn2 '아래를 실행해 다시 시도할 수 있습니다:'
        if ($Server) {
            Write-Warn2 "  `"$adminExe`" enroll --server $Server --key $Key"
        } else {
            Write-Warn2 "  `"$adminExe`" discover     (사내망에서 서버를 찾습니다)"
            Write-Warn2 "  `"$adminExe`" enroll --key $Key"
        }
    }
} elseif ($Server) {
    Write-Warn2 '등록 키(-Key)가 없어 서버 등록을 건너뜁니다.'
    Write-Warn2 '등록 키는 서버의 [설정] 화면에서 확인할 수 있습니다.'
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
    Write-Host "    `"$adminExe`" enroll --key 등록키       (서버는 알아서 찾습니다)"
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
