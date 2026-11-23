@echo off
rem ====================================================================
rem  한일특장 CATIA -> STP 자동 변환 - 매일 밤 9시에 돌도록 Windows 예약 작업에 등록
rem  ※ 이 PC 에 로그인한 사람(CATIA 라이선스를 쓰는 사람)으로 등록됩니다.
rem  ※ 시간을 바꾸려면 아래 /ST 21:00 을 고치세요. 지우기: schtasks /Delete /TN "Hanil CATIA to STP" /F
rem ====================================================================
schtasks /Create /TN "Hanil CATIA to STP" /TR "\"%~dp0run_convert.bat\"" /SC DAILY /ST 21:00 /F
if errorlevel 1 goto bad
echo.
echo 등록했습니다. 매일 21:00 에 CATIA -^> STP 변환이 돕니다.
echo 지금 바로 한 번 돌려 보려면 run_convert.bat 을 더블클릭하세요.
goto end
:bad
echo 등록하지 못했습니다 - 이 파일을 「관리자 권한으로 실행」 해 보세요.
:end
pause
