<#
.SYNOPSIS
    한일 TimeGuard 관리 서버를 설치합니다.

.DESCRIPTION
    사내 PC 한 대에 설치해 두면, 직원 PC 들이 이 서버에서 시간표를 받아 갑니다.
    이 스크립트는 반드시 관리자 권한 PowerShell 에서 실행해야 합니다.

    설치한 PC 는 항상 켜 두어야 합니다.
    (꺼져 있어도 직원 PC 는 마지막으로 받은 시간표를 그대로 적용합니다.)

.PARAMETER Port
    웹 화면과 클라이언트가 접속할 포트. 기본 8443(암호화) 또는 8080(암호화 안 함).

.PARAMETER NoHttps
    암호화를 쓰지 않습니다. 권하지 않습니다.
    사내망에서 비밀번호가 그대로 오갑니다.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install-server.ps1
    powershell -ExecutionPolicy Bypass -File .\install-server.ps1 -Port 9443
#>

[CmdletBinding()]
param(
    [string]$InstallPath = "$env:ProgramFiles\HanilTimeGuardServer",
    [int]$Port = 0,
    [switch]$NoHttps
)

# 포트를 지정하지 않으면 암호화 여부에 맞는 기본값을 쓴다
if ($Port -eq 0) { $Port = if ($NoHttps) { 8080 } else { 8443 } }

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

# --- 인증서와 포트 설정 ---
$settingsPath = Join-Path $InstallPath 'appsettings.json'
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
$certPath = Join-Path $InstallPath 'server-cert.pfx'
$cerPath  = Join-Path $InstallPath '서버인증서.cer'
$scheme   = 'http'

if ($NoHttps) {
    Write-Step "접속 포트를 설정합니다: $Port (암호화 없음)"
    $settings.Kestrel.Endpoints = @{ Http = @{ Url = "http://0.0.0.0:$Port" } }
    Write-Ok '설정했습니다.'
} else {
    Write-Step '통신 암호화를 설정합니다'

    # 이 PC 의 이름과 IP 를 모두 담아 인증서를 만든다.
    # 어느 주소로 접속하든 이름이 맞지 않는다는 오류가 나지 않게 하기 위해서다.
    $names = @($env:COMPUTERNAME, 'localhost')

    # 도메인에 속한 PC 라면 전체 이름도 넣는다. 작업 그룹이면 이 값이 비어 있다.
    if ($env:USERDNSDOMAIN) {
        $names += "$env:COMPUTERNAME.$env:USERDNSDOMAIN"
    }

    $names += (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
               Where-Object { $_.IPAddress -notlike '169.254.*' } |
               Select-Object -ExpandProperty IPAddress)

    $names = $names | Where-Object { $_ -and "$_".Trim() -ne '' } | Select-Object -Unique

    # 기존 인증서가 있으면 다시 쓴다. 새로 만들면 직원 PC 들이 모두 재등록해야 한다.
    $existingCert = Get-ChildItem Cert:\LocalMachine\My |
                    Where-Object { $_.Subject -eq 'CN=HanilTimeGuardServer' } |
                    Sort-Object NotAfter -Descending |
                    Select-Object -First 1

    if ($existingCert -and $existingCert.NotAfter -gt (Get-Date).AddMonths(1)) {
        $cert = $existingCert
        Write-Ok "기존 인증서를 계속 씁니다. (만료: $($cert.NotAfter.ToString('yyyy-MM-dd')))"
    } else {
        $cert = New-SelfSignedCertificate `
                    -Subject 'CN=HanilTimeGuardServer' `
                    -DnsName $names `
                    -CertStoreLocation 'Cert:\LocalMachine\My' `
                    -KeyExportPolicy Exportable `
                    -KeyLength 2048 `
                    -NotAfter (Get-Date).AddYears(10) `
                    -FriendlyName '한일 TimeGuard 관리 서버'
        Write-Ok "인증서를 만들었습니다. (10년 유효)"
    }

    # 서버 PC 자신은 이 인증서를 믿도록 해 둔다. 여기서는 브라우저 경고가 뜨지 않는다.
    $rootStore = New-Object Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
    $rootStore.Open('ReadWrite')
    if (-not ($rootStore.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint })) {
        $rootStore.Add($cert)
    }
    $rootStore.Close()

    # 관리자 PC 에서도 믿을 수 있도록 인증서 파일을 남겨 둔다.
    Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null

    # Kestrel 이 쓸 수 있도록 내보낸다. 비밀번호는 이 PC 안에서만 쓰인다.
    # Get-Random 은 암호용 난수가 아니므로 암호학적 난수 생성기를 쓴다.
    $passwordBytes = New-Object byte[] 24
    $rng = New-Object Security.Cryptography.RNGCryptoServiceProvider
    try { $rng.GetBytes($passwordBytes) } finally { $rng.Dispose() }
    $pfxPassword = [Convert]::ToBase64String($passwordBytes)
    $securePassword = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $certPath -Password $securePassword -Force | Out-Null

    $settings.Kestrel.Endpoints = @{
        Https = @{
            Url = "https://0.0.0.0:$Port"
            Certificate = @{ Path = $certPath; Password = $pfxPassword }
        }
    }

    $scheme = 'https'
    Write-Ok "포트 $Port 에서 암호화된 연결을 받습니다."
}

$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

# 인증서 비밀번호가 들어 있으므로 설정 파일도 관리자만 읽게 한다
$settingsAcl = Get-Acl $settingsPath
$settingsAcl.SetAccessRuleProtection($true, $false)
foreach ($account in @('SYSTEM', 'Administrators')) {
    $settingsAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $account, 'FullControl', 'Allow')))
}
Set-Acl -Path $settingsPath -AclObject $settingsAcl

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
Write-Host "    이 PC 에서   : ${scheme}://localhost:$Port"
if ($address) {
    Write-Host "    다른 PC 에서 : ${scheme}://${address}:$Port"
}
Write-Host ''

if (-not $NoHttps) {
    Write-Host '  다른 PC 에서 접속할 때 인증서 경고가 뜬다면' -ForegroundColor White
    Write-Host "    아래 파일을 그 PC 로 복사해 두 번 클릭 → [인증서 설치]"
    Write-Host "    → [로컬 컴퓨터] → [신뢰할 수 있는 루트 인증 기관] 선택"
    Write-Host "      $cerPath" -ForegroundColor Gray
    Write-Host '    (경고를 무시하고 계속 진행해도 통신은 암호화됩니다.)'
    Write-Host ''
}

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
Write-Host '    4) [설정] 화면에서 [지금 이 PC 에서만 열리도록 설정] 을 눌러 접근 제한'
Write-Host '    5) [설정] 화면에 나오는 설치 명령 한 줄을 복사해 직원 PC 에서 실행'
Write-Host ''
Write-Host '  직원 PC 설치 명령 (서버 [설정] 화면에도 나옵니다)' -ForegroundColor White
if ($address) {
    Write-Host "    .\install.ps1 -Server ${scheme}://${address}:$Port -Key <등록키>"
}
Write-Host ''
