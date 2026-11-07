@echo off
rem ====================================================================
rem  한일특장 CATIA -> STP 자동 변환 (CATIA 가 깔린 PC 에서)
rem  CATIA 를 화면 없이 띄워 CATIA_to_STP.CATScript 를 돌립니다.
rem  ※ 이 파일과 CATIA_to_STP.CATScript 를 같은 폴더(예: C:\HanilCATIA)에 두세요.
rem ====================================================================

rem ===== 여기만 고치세요 ===============================================
rem  원본 CATIA 폴더(하위 폴더까지)와 STP 를 저장할 폴더 - NAS 주소도 됩니다
set "HANIL_STP_SRC=\\NAS\도면\CATIA"
set "HANIL_STP_OUT=\\NAS\도면\STP"
rem  CATIA 위치 - 비워 두면 자동으로 찾습니다. 못 찾으면 직접 적으세요.
rem   예) set "CNEXT=C:\Program Files\Dassault Systemes\B28\win_b64\code\bin\CNEXT.exe"
rem   예) set "CATENV=CATIA.V5-6R2018.B28"
set "CNEXT="
set "CATENV="
set "CATENVDIR=C:\ProgramData\DassaultSystemes\CATEnv"
rem =====================================================================

set "HANIL_STP_BATCH=1"
if not defined CNEXT for /d %%D in ("C:\Program Files\Dassault Systemes\B*") do if exist "%%D\win_b64\code\bin\CNEXT.exe" set "CNEXT=%%D\win_b64\code\bin\CNEXT.exe"
if not defined CNEXT for /d %%D in ("C:\Program Files\Dassault Systemes\B*") do if exist "%%D\intel_a\code\bin\CNEXT.exe" set "CNEXT=%%D\intel_a\code\bin\CNEXT.exe"
if not defined CNEXT goto nocatia
if not defined CATENV for %%F in ("%CATENVDIR%\*.txt") do set "CATENV=%%~nF"
if not defined CATENV goto noenv

echo [%date% %time%] CATIA -^> STP 변환 시작
echo   원본: %HANIL_STP_SRC%
echo   저장: %HANIL_STP_OUT%
echo   CATIA: %CNEXT%  (환경 %CATENV%)
"%CNEXT%" -env %CATENV% -direnv "%CATENVDIR%" -batch -macro "%~dp0CATIA_to_STP.CATScript"
echo [%date% %time%] 끝 - 결과는 %HANIL_STP_OUT%\변환기록.txt
goto end

:nocatia
echo CATIA(CNEXT.exe)를 찾지 못했습니다. 이 파일 위쪽 CNEXT= 에 위치를 적어 주세요.
goto end
:noenv
echo CATIA 환경 파일을 찾지 못했습니다(%CATENVDIR%). 이 파일 위쪽 CATENV= 에 환경 이름을 적어 주세요.
:end
