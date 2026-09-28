//go:build windows

package main

import (
	"encoding/base64"
	"os/exec"
	"path/filepath"
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
	u := utf16.Encode([]rune(ps))
	b := make([]byte, len(u)*2)
	for i, r := range u {
		b[i*2] = byte(r)
		b[i*2+1] = byte(r >> 8)
	}
	c := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
		"-EncodedCommand", base64.StdEncoding.EncodeToString(b))
	hideWindow(c)
	_ = c.Run()
}
