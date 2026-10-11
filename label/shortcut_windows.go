//go:build windows

package main

import (
	"encoding/base64"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"unicode/utf16"
)

// ── 바탕화면 아이콘 ─────────────────────────────────────────
//
//	⭐ 켤 때마다 확인해 **없으면 만들고, exe 를 옮겼으면 고쳐** 둔다.
//	  현장에서 «아이콘이 없어졌다» 로 전화가 오지 않게.
//	  시작 메뉴에도 같이 넣는다(바탕화면을 정리해도 찾을 수 있게).
//	⚠ 윈도우 바로가기(.lnk)는 표준 라이브러리로 못 만든다 → 윈도우에 들어 있는 PowerShell 에 맡긴다.
//	  명령은 -EncodedCommand 로 넘긴다(한글·빈칸이 든 경로도 깨지지 않게).
func ensureShortcuts(exe string, autostart bool) {
	q := func(s string) string { return "'" + strings.ReplaceAll(s, "'", "''") + "'" }
	auto := "$false"
	if autostart {
		auto = "$true"
	}
	ps := `$ErrorActionPreference='SilentlyContinue'
$W=New-Object -ComObject WScript.Shell
$exe=` + q(exe) + `
$dir=` + q(filepath.Dir(exe)) + `
$name=` + q(shortcutName+".lnk") + `
function Put($folder){
  if(-not $folder){ return }
  $p=Join-Path $folder $name
  if((Test-Path $p) -and ($W.CreateShortcut($p).TargetPath -eq $exe)){ return }
  $s=$W.CreateShortcut($p); $s.TargetPath=$exe; $s.WorkingDirectory=$dir
  $s.IconLocation="$exe,0"; $s.Description='현장 라벨 발행'; $s.Save()
}
Put ([Environment]::GetFolderPath('Desktop'))
Put ([Environment]::GetFolderPath('Programs'))
$st=[Environment]::GetFolderPath('Startup')
if(` + auto + `){ Put $st } elseif($st){ Remove-Item (Join-Path $st $name) -ErrorAction SilentlyContinue }
`
	runPS(ps)
}

func runPS(ps string) string {
	u := utf16.Encode([]rune(ps))
	b := make([]byte, len(u)*2)
	for i, r := range u {
		b[i*2] = byte(r)
		b[i*2+1] = byte(r >> 8)
	}
	c := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
		"-EncodedCommand", base64.StdEncoding.EncodeToString(b))
	hideWindow(c)
	out, err := c.Output()
	if err != nil {
		return strings.TrimSpace(string(out)) + " (" + err.Error() + ")"
	}
	return strings.TrimSpace(string(out))
}

// ── 남아 있는 것 치우기 ─────────────────────────────────────
//
//	⚠⚠ 창을 닫아도 Edge 는 뒤에 프로세스를 남겨 둘 때가 있다(시작 부스트·백그라운드 실행).
//	  이 프로그램 자리(프로필)를 쥔 채 남은 Edge 에 새 창을 붙이면 **빈 창**이 뜬다.
//	  또 예전 판 hanil-label 이 뒤에 살아 있으면 새 판 대신 그것이 창을 띄운다.
//	⭐ 그래서 관문을 새로 열 때(= 이 프로그램이 처음 켜질 때) 둘 다 내린다.
//	  ⚠ 이 프로그램 자리(HanilLabel)를 쓰는 Edge·Chrome 만 — 직원이 쓰는 Edge 는 건드리지 않는다.
func cleanupStale(prof string, pid int, killOld bool) string {
	q := func(s string) string { return "'" + strings.ReplaceAll(s, "'", "''") + "'" }
	old := "$false"
	if killOld {
		old = "$true"
	}
	ps := `$ErrorActionPreference='SilentlyContinue'
$prof=` + q(prof) + `
$n=0; $o=0
Get-CimInstance Win32_Process -Filter "Name='msedge.exe' OR Name='chrome.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($prof, [StringComparison]::OrdinalIgnoreCase) -ge 0 } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $n++ }
if(` + old + `){ Get-Process | Where-Object { $_.ProcessName -like 'hanil-label*' -and $_.Id -ne ` + strconv.Itoa(pid) + ` } | ForEach-Object { Stop-Process -Id $_.Id -Force; $o++ } }
Start-Sleep -Milliseconds 400
"browser=$n old=$o"
`
	return runPS(ps)
}

// 바탕화면 아이콘이 지금 가리키는 exe 의 폴더(예전 설정 파일을 찾으려고)
func oldShortcutDir() string {
	out := runPS(`$ErrorActionPreference='SilentlyContinue'
$p=Join-Path ([Environment]::GetFolderPath('Desktop')) ` + "'" + strings.ReplaceAll(shortcutName, "'", "''") + ".lnk'" + `
if(Test-Path $p){ (New-Object -ComObject WScript.Shell).CreateShortcut($p).TargetPath }`)
	out = strings.TrimSpace(out)
	if out == "" || strings.Contains(out, "exit status") {
		return ""
	}
	return filepath.Dir(out)
}
