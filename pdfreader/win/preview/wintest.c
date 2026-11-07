// 탐색기 흉내 시험 — wintest.exe <dll> <pdf> <출력 폴더>
//  ① 썸네일: IThumbnailProvider::GetThumbnail(256) → thumb.bmp
//  ② 미리 보기 창: SetWindow·DoPreview → 창 그림을 preview.bmp 로(WM_PRINTCLIENT)
//  ③ DllRegisterServer → HKCU 에 들어갔나
#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <shlwapi.h>
#include <shobjidl.h>
#include <thumbcache.h>
#include <propsys.h>
#include <stdio.h>
DEFINE_GUID(CLSID_P, 0x3e479ebb, 0x0fe9, 0x495f, 0xb4, 0x80, 0xf8, 0x47, 0x0d, 0xa5, 0x11, 0x3b);
DEFINE_GUID(CLSID_T, 0x083f7f9f, 0x854e, 0x4108, 0x97, 0xe5, 0x4d, 0x7a, 0x46, 0x1d, 0xed, 0x48);
typedef HRESULT (__stdcall *GCO)(REFCLSID, REFIID, void **);
static int saveBmp(HBITMAP hb, const char *path) {
  BITMAP b; GetObject(hb, sizeof b, &b);
  BITMAPINFO bi = { { sizeof(BITMAPINFOHEADER), b.bmWidth, -b.bmHeight, 1, 32, BI_RGB } };
  int sz = b.bmWidth * b.bmHeight * 4;
  BYTE *px = malloc(sz);
  HDC dc = GetDC(NULL);
  GetDIBits(dc, hb, 0, b.bmHeight, px, &bi, DIB_RGB_COLORS);
  ReleaseDC(NULL, dc);
  FILE *f = fopen(path, "wb"); if (!f) return 0;
  BITMAPFILEHEADER fh = { 0x4d42, sizeof fh + sizeof(BITMAPINFOHEADER) + sz, 0, 0, sizeof fh + sizeof(BITMAPINFOHEADER) };
  fwrite(&fh, sizeof fh, 1, f); fwrite(&bi.bmiHeader, sizeof(BITMAPINFOHEADER), 1, f); fwrite(px, sz, 1, f); fclose(f);
  long dark = 0; for (int i = 0; i < sz; i += 4) if (px[i] < 100 && px[i + 1] < 100) dark++;
  free(px);
  printf("  %s %dx%d 어두운 점 %ld\n", path, b.bmWidth, b.bmHeight, dark);
  return dark > 50;
}
int main(int argc, char **argv) {
  if (argc < 4) return 2;
  CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
  HMODULE m = LoadLibraryA(argv[1]);
  if (!m) { printf("FAIL LoadLibrary %lu\n", GetLastError()); return 1; }
  GCO gco = (GCO)GetProcAddress(m, "DllGetClassObject");
  FILE *f = fopen(argv[2], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  BYTE *data = malloc(n); fread(data, 1, n, f); fclose(f);
  char out[MAX_PATH]; int fails = 0;
  // ① 썸네일
  IClassFactory *cf = NULL; IThumbnailProvider *tp = NULL; IInitializeWithStream *ini = NULL;
  HRESULT hr = gco(&CLSID_T, &IID_IClassFactory, (void **)&cf);
  if (SUCCEEDED(hr)) hr = IClassFactory_CreateInstance(cf, NULL, &IID_IThumbnailProvider, (void **)&tp);
  if (SUCCEEDED(hr)) hr = IThumbnailProvider_QueryInterface(tp, &IID_IInitializeWithStream, (void **)&ini);
  IStream *st = SHCreateMemStream(data, n);
  if (SUCCEEDED(hr)) hr = IInitializeWithStream_Initialize(ini, st, STGM_READ);
  HBITMAP hb = NULL; WTS_ALPHATYPE at;
  if (SUCCEEDED(hr)) hr = IThumbnailProvider_GetThumbnail(tp, 256, &hb, &at);
  sprintf(out, "%s\\thumb.bmp", argv[3]);
  if (SUCCEEDED(hr) && hb && saveBmp(hb, out)) printf("OK 썸네일\n"); else { printf("FAIL 썸네일 hr=%08lx\n", hr); fails++; }
  if (ini) IInitializeWithStream_Release(ini); if (tp) IThumbnailProvider_Release(tp); if (cf) IClassFactory_Release(cf); IStream_Release(st);
  // ② 미리 보기 창
  WNDCLASSA wc = { 0, DefWindowProcA, 0, 0, GetModuleHandle(NULL), NULL, NULL, NULL, NULL, "host" };
  RegisterClassA(&wc);
  HWND host = CreateWindowA("host", "host", WS_OVERLAPPEDWINDOW, 0, 0, 520, 700, NULL, NULL, NULL, NULL);
  IPreviewHandler *ph = NULL; IInitializeWithStream *pi = NULL; IOleWindow *ow = NULL;
  cf = NULL;
  hr = gco(&CLSID_P, &IID_IClassFactory, (void **)&cf);
  if (SUCCEEDED(hr)) hr = IClassFactory_CreateInstance(cf, NULL, &IID_IPreviewHandler, (void **)&ph);
  if (SUCCEEDED(hr)) hr = IPreviewHandler_QueryInterface(ph, &IID_IInitializeWithStream, (void **)&pi);
  st = SHCreateMemStream(data, n);
  if (SUCCEEDED(hr)) hr = IInitializeWithStream_Initialize(pi, st, STGM_READ);
  RECT rc = { 0, 0, 500, 660 };
  if (SUCCEEDED(hr)) hr = IPreviewHandler_SetWindow(ph, host, &rc);
  if (SUCCEEDED(hr)) hr = IPreviewHandler_DoPreview(ph);
  HWND w = NULL;
  if (SUCCEEDED(hr)) hr = IPreviewHandler_QueryInterface(ph, &IID_IOleWindow, (void **)&ow);
  if (SUCCEEDED(hr)) hr = IOleWindow_GetWindow(ow, &w);
  if (SUCCEEDED(hr) && w) {
    RECT r; GetClientRect(w, &r);
    HDC dc = GetDC(NULL), mdc = CreateCompatibleDC(dc);
    HBITMAP mb = CreateCompatibleBitmap(dc, r.right, r.bottom);
    SelectObject(mdc, mb);
    SendMessageA(w, WM_PRINTCLIENT, (WPARAM)mdc, PRF_CLIENT);
    DeleteDC(mdc); ReleaseDC(NULL, dc);
    sprintf(out, "%s\\preview.bmp", argv[3]);
    if (saveBmp(mb, out)) printf("OK 미리 보기 창 %ldx%ld\n", r.right, r.bottom); else { printf("FAIL 미리 보기 그림 비었음\n"); fails++; }
    // 바퀴로 넘기기
    SendMessageA(w, WM_MOUSEWHEEL, MAKEWPARAM(0, (WORD)(-120 * 8)), 0);
    SCROLLINFO si = { sizeof si, SIF_POS }; GetScrollInfo(w, SB_VERT, &si);
    printf("%s 바퀴 → 스크롤 %d\n", si.nPos > 0 ? "OK" : "FAIL", si.nPos); if (si.nPos <= 0) fails++;
  } else { printf("FAIL 미리 보기 hr=%08lx\n", hr); fails++; }
  if (ph) { IPreviewHandler_Unload(ph); }
  if (ow) IOleWindow_Release(ow); if (pi) IInitializeWithStream_Release(pi); if (ph) IPreviewHandler_Release(ph); if (cf) IClassFactory_Release(cf);
  // ③ 등록
  HRESULT (__stdcall *reg)(void) = (void *)GetProcAddress(m, "DllRegisterServer");
  hr = reg();
  HKEY k; char v[300]; DWORD vl = sizeof v;
  LONG r1 = RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\Classes\\.pdf\\shellex\\{8895b1c6-b41f-4c1c-a562-0d564250836f}", 0, KEY_READ, &k);
  if (!r1) { RegQueryValueExA(k, NULL, NULL, NULL, (BYTE *)v, &vl); RegCloseKey(k); }
  if (SUCCEEDED(hr) && !r1 && !strcmp(v, "{3E479EBB-0FE9-495F-B480-F8470DA5113B}")) printf("OK 등록(HKCU)\n"); else { printf("FAIL 등록 hr=%08lx r=%ld\n", hr, r1); fails++; }
  printf(fails ? "실패 %d\n" : "모두 통과\n", fails);
  return fails;
}
