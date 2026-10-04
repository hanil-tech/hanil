# ✍🛡 사내 서명 인증서 만들기 — 윈도우에서 **한 번만** 하면 됩니다.
#
#  무엇에 쓰나
#    이 인증서로 설치 파일에 서명해 두면, 직원 PC 에서
#    「Windows 의 PC 보호 · 확인되지 않은 게시자」 경고가 **뜨지 않습니다.**
#    (설치 프로그램이 이 인증서를 그 PC 가 믿도록 함께 등록해 주기 때문입니다.)
#
#  쓰는 법
#    ① 이 파일을 마우스 오른쪽 버튼 → [PowerShell 에서 실행]
#       (또는 PowerShell 을 열고)  powershell -ExecutionPolicy Bypass -File .\build\인증서-만들기.ps1
#    ② 비밀번호를 하나 정해서 넣습니다(잊어버리면 처음부터 다시 만들어야 합니다).
#    ③ 화면에 나오는 대로 두 가지를 하면 끝입니다.
#
#  ⚠⚠⚠ 비밀 열쇠(.pfx)는 **저장소에 올리지 마십시오.**
#    이 저장소는 누구나 볼 수 있습니다. 열쇠가 새면 그것으로 서명한
#    **아무 프로그램이나** 우리 회사 PC 들이 믿게 됩니다.
#    저장소에 함께 두는 것은 **공개용(.cer)** 뿐입니다 — 그것으로는 서명하지 못합니다.

$ErrorActionPreference = 'Stop'

$root     = Split-Path -Parent $PSScriptRoot
$certDir  = Join-Path $root 'cert'
$cerPath  = Join-Path $certDir 'hanil-code-signing.cer'
$pfxPath  = Join-Path $certDir 'hanil-code-signing.pfx'

New-Item -ItemType Directory -Force -Path $certDir | Out-Null

if (Test-Path $pfxPath) {
    Write-Host ''
    Write-Host "이미 만들어 둔 인증서가 있습니다: $pfxPath" -ForegroundColor Yellow
    Write-Host '다시 만들면 **예전 것으로 서명한 프로그램은 경고가 다시 뜹니다.**'
    $again = Read-Host '그래도 새로 만들까요? (y/N)'
    if ($again -ne 'y') { Write-Host '그만둡니다.'; exit 0 }
}

Write-Host ''
Write-Host '== 한일 TimeGuard 서명 인증서 만들기 ==' -ForegroundColor Cyan
Write-Host ''
$password = Read-Host '인증서 비밀번호를 정하세요 (적어 두십시오)' -AsSecureString

#  ⚠ 10년짜리로 만든다. 기한이 지나면 그 뒤에 서명한 것부터 경고가 다시 뜬다.
#    (이미 서명해 둔 것은 타임스탬프 덕분에 그대로 유효하다.)
$certificate = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject 'CN=한일특장(주), O=한일특장(주), C=KR' `
    -KeyUsage DigitalSignature `
    -KeyAlgorithm RSA -KeyLength 3072 `
    -CertStoreLocation 'Cert:\CurrentUser\My' `
    -NotAfter (Get-Date).AddYears(10) `
    -FriendlyName '한일 TimeGuard 코드 서명'

Export-PfxCertificate -Cert $certificate -FilePath $pfxPath -Password $password | Out-Null
Export-Certificate  -Cert $certificate -FilePath $cerPath -Type CERT | Out-Null

$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($pfxPath))
$base64Path = Join-Path $certDir '깃허브에-넣을-값.txt'
Set-Content -Path $base64Path -Value $base64 -Encoding ascii

Write-Host ''
Write-Host '✅ 만들었습니다.' -ForegroundColor Green
Write-Host ''
Write-Host "  공개용(저장소에 올립니다)  : $cerPath"
Write-Host "  비밀 열쇠(올리지 마십시오) : $pfxPath"
Write-Host "  깃허브에 넣을 값           : $base64Path"
Write-Host ''
Write-Host '== 이제 두 가지만 하시면 됩니다 ==' -ForegroundColor Cyan
Write-Host ''
Write-Host '① 공개용 인증서를 저장소에 넣기'
Write-Host '     cert\hanil-code-signing.cer 를 커밋해 주세요.'
Write-Host '     (설치 파일 안에 함께 담겨, 직원 PC 가 우리 인증서를 믿게 해 줍니다)'
Write-Host ''
Write-Host '② 깃허브에 비밀값 두 개 넣기'
Write-Host '     깃허브 저장소 → Settings → Secrets and variables → Actions → New repository secret'
Write-Host ''
Write-Host '     이름: SIGN_PFX_BASE64     값: 위 「깃허브에-넣을-값.txt」 의 내용 전체'
Write-Host '     이름: SIGN_PFX_PASSWORD   값: 방금 정한 비밀번호'
Write-Host ''
Write-Host '그다음부터 [Actions] 에서 구우면 **서명된 설치 파일**이 나옵니다.' -ForegroundColor Green
Write-Host ''
Write-Host '⚠ cert\hanil-code-signing.pfx 와 깃허브에-넣을-값.txt 는 저장소에 올리지 마십시오.' -ForegroundColor Yellow
Write-Host '  (.gitignore 에 이미 적어 두었습니다)'
Write-Host ''
