//go:build windows

package main

import (
	"encoding/base64"
	"os/exec"
	"path/filepath"
	"strings"
	"unicode/utf16"
)

// ── 바탕화면·시작 메뉴·시작프로그램 아이콘 ───────────────────
//
//	⭐ 켤 때마다 확인해 **없으면 만들고, exe 를 옮겼으면 고쳐** 둔다(라벨 발행기와 같은 방식).
//	  바탕화면 달력은 윈도우가 켜질 때 같이 떠야 쓸모가 있다 → 시작프로그램(AUTOSTART=1)이 기본.
//	⚠ 윈도우 바로가기(.lnk)는 표준 라이브러리로 못 만든다 → 윈도우에 들어 있는 PowerShell 에 맡긴다.
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
  $s.IconLocation="$exe,0"; $s.Description='바탕화면 달력 · 포털 결재·알림'; $s.Save()
}
Put ([Environment]::GetFolderPath('Desktop'))
Put ([Environment]::GetFolderPath('Programs'))
$st=[Environment]::GetFolderPath('Startup')
if(` + auto + `){ Put $st } elseif($st){ Remove-Item (Join-Path $st $name) -ErrorAction SilentlyContinue }
`
	logf("아이콘: %s", runPS(ps))
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
