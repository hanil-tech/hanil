//go:build !windows

package main

// 윈도우가 아니면 DPAPI 가 없다 — 시험용으로 그대로 둔다
func protect(b []byte) ([]byte, error)   { return append([]byte(nil), b...), nil }
func unprotect(b []byte) ([]byte, error) { return append([]byte(nil), b...), nil }
