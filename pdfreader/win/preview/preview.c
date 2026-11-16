// 📕 한일 PDF 리더 — 탐색기 미리 보기(미리 보기 창) · 미리 보기 그림(큰 아이콘)
//
//  윈도우 탐색기가 불러 쓰는 확장(COM DLL)이다.
//   · 미리 보기 창(Alt+P): IPreviewHandler — 쪽을 아래로 이어 그리고, 바퀴·스크롤 막대로 넘긴다.
//   · 큰 아이콘·썸네일: IThumbnailProvider — 첫 쪽을 그림으로.
//  PDF 그리기는 같은 폴더의 pdfium.dll(구글 PDFium, BSD-3)을 실행할 때 불러 쓴다.
//  ⚠ PDFium 은 한 번에 하나씩만 — 모든 호출을 잠금(g_lock) 안에서 한다(탐색기는 썸네일을 여러 일꾼으로 부른다).
//  ⚠ 파일 대신 스트림(IInitializeWithStream)으로 받는다 — 탐색기가 권하는 방식(격리된 prevhost/dllhost 에서 돈다).
//
//  등록(사용자 단위 HKCU — 관리자 권한 없이): regsvr32 /s hanil-pdf-preview.dll
//  해제: regsvr32 /u /s hanil-pdf-preview.dll
#define COBJMACROS
#define WIN32_LEAN_AND_MEAN
#define INITGUID
#include <windows.h>
#include <ole2.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <thumbcache.h>
#include <propsys.h>
#include <ocidl.h>
#include <stddef.h>

// {3E479EBB-0FE9-495F-B480-F8470DA5113B} 미리 보기 창
DEFINE_GUID(CLSID_HanilPreview, 0x3e479ebb, 0x0fe9, 0x495f, 0xb4, 0x80, 0xf8, 0x47, 0x0d, 0xa5, 0x11, 0x3b);
// {083F7F9F-854E-4108-97E5-4D7A461DED48} 미리 보기 그림(썸네일)
DEFINE_GUID(CLSID_HanilThumb, 0x083f7f9f, 0x854e, 0x4108, 0x97, 0xe5, 0x4d, 0x7a, 0x46, 0x1d, 0xed, 0x48);
#define S_PREVIEW L"{3E479EBB-0FE9-495F-B480-F8470DA5113B}"
#define S_THUMB L"{083F7F9F-854E-4108-97E5-4D7A461DED48}"
#define S_IPREVIEW L"{8895b1c6-b41f-4c1c-a562-0d564250836f}"
#define S_ITHUMB L"{e357fccd-a995-4576-b01f-234630154e96}"
#define S_PREVHOST_APPID L"{6d2b5079-2f0b-48dd-ab7f-97cec514d30b}"

static HINSTANCE g_inst;
static LONG g_objs, g_locks;
static CRITICAL_SECTION g_lock;

// ───────────── PDFium (실행할 때 불러옴) ─────────────
typedef void *FPDF_DOCUMENT, *FPDF_PAGE, *FPDF_BITMAP;
static struct {
  int ok;
  void (__stdcall *InitLibrary)(void);
  FPDF_DOCUMENT (__stdcall *LoadMemDocument)(const void *, int, const char *);
  void (__stdcall *CloseDocument)(FPDF_DOCUMENT);
  int (__stdcall *GetPageCount)(FPDF_DOCUMENT);
  int (__stdcall *GetPageSizeByIndex)(FPDF_DOCUMENT, int, double *, double *);
  FPDF_PAGE (__stdcall *LoadPage)(FPDF_DOCUMENT, int);
  void (__stdcall *ClosePage)(FPDF_PAGE);
  FPDF_BITMAP (__stdcall *BitmapCreate)(int, int, int);
  void (__stdcall *BitmapFillRect)(FPDF_BITMAP, int, int, int, int, unsigned long);
  void *(__stdcall *BitmapGetBuffer)(FPDF_BITMAP);
  int (__stdcall *BitmapGetStride)(FPDF_BITMAP);
  void (__stdcall *BitmapDestroy)(FPDF_BITMAP);
  void (__stdcall *RenderPageBitmap)(FPDF_BITMAP, FPDF_PAGE, int, int, int, int, int, int);
  unsigned long (__stdcall *GetLastError)(void);
} P;

static int pdfium(void) {
  if (P.ok) return P.ok > 0;
  WCHAR path[MAX_PATH];
  DWORD n = GetModuleFileNameW(g_inst, path, MAX_PATH);
  while (n && path[n - 1] != L'\\') n--;
  path[n] = 0;
  lstrcatW(path, L"pdfium.dll");
  HMODULE m = LoadLibraryExW(path, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
  if (!m) { P.ok = -1; return 0; }
#define F(field, name) if (!(*(FARPROC *)&P.field = GetProcAddress(m, name))) { P.ok = -1; return 0; }
  F(InitLibrary, "FPDF_InitLibrary") F(LoadMemDocument, "FPDF_LoadMemDocument") F(CloseDocument, "FPDF_CloseDocument")
  F(GetPageCount, "FPDF_GetPageCount") F(GetPageSizeByIndex, "FPDF_GetPageSizeByIndex") F(LoadPage, "FPDF_LoadPage")
  F(ClosePage, "FPDF_ClosePage") F(BitmapCreate, "FPDFBitmap_Create") F(BitmapFillRect, "FPDFBitmap_FillRect")
  F(BitmapGetBuffer, "FPDFBitmap_GetBuffer") F(BitmapGetStride, "FPDFBitmap_GetStride") F(BitmapDestroy, "FPDFBitmap_Destroy")
  F(RenderPageBitmap, "FPDF_RenderPageBitmap") F(GetLastError, "FPDF_GetLastError")
#undef F
  P.InitLibrary();
  P.ok = 1;
  return 1;
}
#define FPDF_ANNOT 0x01
#define FPDF_LCD_TEXT 0x02

//  스트림을 통째로 읽는다(최대 1GB)
static HRESULT readStream(IStream *s, BYTE **out, DWORD *len) {
  STATSTG st;
  ULONGLONG size = 0;
  if (SUCCEEDED(IStream_Stat(s, &st, STATFLAG_NONAME))) size = st.cbSize.QuadPart;
  if (size > (1ull << 30)) return E_OUTOFMEMORY;
  DWORD cap = size ? (DWORD)size : (1u << 20), have = 0;
  BYTE *buf = HeapAlloc(GetProcessHeap(), 0, cap);
  if (!buf) return E_OUTOFMEMORY;
  for (;;) {
    if (have == cap) {
      if (cap >= (1u << 30)) break;
      BYTE *nb = HeapReAlloc(GetProcessHeap(), 0, buf, cap * 2);
      if (!nb) { HeapFree(GetProcessHeap(), 0, buf); return E_OUTOFMEMORY; }
      buf = nb; cap *= 2;
    }
    ULONG got = 0;
    HRESULT hr = IStream_Read(s, buf + have, cap - have, &got);
    have += got;
    if (FAILED(hr)) { HeapFree(GetProcessHeap(), 0, buf); return hr; }
    if (got == 0 || hr == S_FALSE) break;
  }
  *out = buf; *len = have;
  return S_OK;
}

//  한 쪽을 w×h 로 그린 BGRA(위에서 아래) — 잠금 안에서 부른다
static FPDF_BITMAP renderPage(FPDF_DOCUMENT doc, int i, int w, int h) {
  FPDF_PAGE pg = P.LoadPage(doc, i);
  if (!pg) return NULL;
  FPDF_BITMAP bm = P.BitmapCreate(w, h, 0);
  if (bm) {
    P.BitmapFillRect(bm, 0, 0, w, h, 0xFFFFFFFF);
    P.RenderPageBitmap(bm, pg, 0, 0, w, h, 0, FPDF_ANNOT | FPDF_LCD_TEXT);
  }
  P.ClosePage(pg);
  return bm;
}

// ───────────── 미리 보기 창 ─────────────
#define MAXCACHE 4096
typedef struct Preview {
  IPreviewHandlerVtbl *vPrev;
  IInitializeWithStreamVtbl *vInit;
  IObjectWithSiteVtbl *vSite;
  IOleWindowVtbl *vWin;
  IPreviewHandlerVisualsVtbl *vVis;
  LONG ref;
  IUnknown *site;
  HWND parent, hwnd;
  RECT rc;
  BYTE *data; DWORD size;
  FPDF_DOCUMENT doc;
  int pages, err;
  double *pw, *ph;          //  쪽 크기(pt)
  int *top;                 //  쪽마다 위쪽 자리(px, 지금 너비 기준)
  int width, total, scroll;
  FPDF_BITMAP *cache; int *cacheW;
  COLORREF bg, fg;
} Preview;

#define FROM(T, field, p) ((T *)((BYTE *)(p) - offsetof(T, field)))
static const WCHAR WNDCLASS_NAME[] = L"HanilPdfPreviewWnd";
static LRESULT CALLBACK wndProc(HWND, UINT, WPARAM, LPARAM);

static void layout(Preview *p) {
  RECT r; GetClientRect(p->hwnd, &r);
  int w = r.right - r.left - 16;
  if (w < 40) w = 40;
  if (w != p->width) {
    p->width = w;
    EnterCriticalSection(&g_lock);
    for (int i = 0; i < p->pages; i++) if (p->cache[i]) { P.BitmapDestroy(p->cache[i]); p->cache[i] = NULL; }
    LeaveCriticalSection(&g_lock);
  }
  int y = 8;
  for (int i = 0; i < p->pages; i++) { p->top[i] = y; y += (int)(p->ph[i] * w / p->pw[i]) + 8; }
  p->total = y;
  int view = r.bottom - r.top;
  if (p->scroll > p->total - view) p->scroll = p->total - view;
  if (p->scroll < 0) p->scroll = 0;
  SCROLLINFO si = { sizeof si, SIF_RANGE | SIF_PAGE | SIF_POS, 0, p->total, (UINT)view, p->scroll };
  SetScrollInfo(p->hwnd, SB_VERT, &si, TRUE);
}
static void freeDoc(Preview *p) {
  EnterCriticalSection(&g_lock);
  if (p->cache) for (int i = 0; i < p->pages; i++) if (p->cache[i]) P.BitmapDestroy(p->cache[i]);
  if (p->doc) P.CloseDocument(p->doc);
  LeaveCriticalSection(&g_lock);
  HeapFree(GetProcessHeap(), 0, p->cache); HeapFree(GetProcessHeap(), 0, p->pw); HeapFree(GetProcessHeap(), 0, p->ph); HeapFree(GetProcessHeap(), 0, p->top);
  p->cache = NULL; p->pw = p->ph = NULL; p->top = NULL; p->doc = NULL; p->pages = 0;
}
static void paint(Preview *p, HDC dc) {
  RECT r; GetClientRect(p->hwnd, &r);
  HBRUSH b = CreateSolidBrush(p->bg); FillRect(dc, &r, b); DeleteObject(b);
  SetBkMode(dc, TRANSPARENT);
  SetTextColor(dc, p->fg);
  HFONT f = CreateFontW(-14, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Malgun Gothic");
  HFONT of = SelectObject(dc, f);
  if (p->err || !p->pages) {
    const WCHAR *msg = p->err == 4 ? L"암호가 걸린 PDF 라 미리 볼 수 없습니다" : p->err == -1 ? L"pdfium.dll 을 찾지 못했습니다 — 한일 PDF 리더를 다시 설치하세요" : L"미리 볼 수 없는 PDF 입니다(손상되었거나 PDF 가 아님)";
    DrawTextW(dc, msg, -1, &r, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_WORDBREAK);
  } else {
    int view = r.bottom, first = -1;
    for (int i = 0; i < p->pages; i++) {
      int h = (int)(p->ph[i] * p->width / p->pw[i]);
      int y = p->top[i] - p->scroll;
      if (y + h < 0 || y > view) {
        //  멀리 간 쪽 그림은 버린다(메모리)
        if (p->cache[i] && (y + h < -3 * view || y > 4 * view)) { EnterCriticalSection(&g_lock); P.BitmapDestroy(p->cache[i]); LeaveCriticalSection(&g_lock); p->cache[i] = NULL; }
        continue;
      }
      if (first < 0) first = i;
      if (!p->cache[i] || p->cacheW[i] != p->width) {
        EnterCriticalSection(&g_lock);
        if (p->cache[i]) P.BitmapDestroy(p->cache[i]);
        p->cache[i] = renderPage(p->doc, i, p->width, h);
        LeaveCriticalSection(&g_lock);
        p->cacheW[i] = p->width;
      }
      if (p->cache[i]) {
        BITMAPINFO bi = { { sizeof(BITMAPINFOHEADER), P.BitmapGetStride(p->cache[i]) / 4, -h, 1, 32, BI_RGB } };
        SetDIBitsToDevice(dc, 8, y, p->width, h, 0, 0, 0, h, P.BitmapGetBuffer(p->cache[i]), &bi, DIB_RGB_COLORS);
      }
    }
    //  오른쪽 위: 「1 / 12 · 한일 PDF 리더」
    WCHAR t[96];
    wsprintfW(t, L" %d / %d 쪽 · 한일 PDF 리더 ", first < 0 ? 1 : first + 1, p->pages);
    SIZE sz; GetTextExtentPoint32W(dc, t, lstrlenW(t), &sz);
    RECT tr = { r.right - sz.cx - 14, 2, r.right - 6, 2 + sz.cy + 4 };
    HBRUSH tb = CreateSolidBrush(RGB(60, 60, 60)); FillRect(dc, &tr, tb); DeleteObject(tb);
    SetTextColor(dc, RGB(255, 255, 255));
    DrawTextW(dc, t, -1, &tr, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
  }
  SelectObject(dc, of); DeleteObject(f);
}
static void scrollTo(Preview *p, int y) {
  RECT r; GetClientRect(p->hwnd, &r);
  int max = p->total - (r.bottom - r.top);
  if (y > max) y = max;
  if (y < 0) y = 0;
  if (y == p->scroll) return;
  p->scroll = y;
  SetScrollPos(p->hwnd, SB_VERT, y, TRUE);
  InvalidateRect(p->hwnd, NULL, FALSE);
}
static LRESULT CALLBACK wndProc(HWND h, UINT m, WPARAM w, LPARAM l) {
  Preview *p = (Preview *)GetWindowLongPtrW(h, GWLP_USERDATA);
  switch (m) {
  case WM_NCCREATE: SetWindowLongPtrW(h, GWLP_USERDATA, (LONG_PTR)((CREATESTRUCTW *)l)->lpCreateParams); break;
  case WM_ERASEBKGND: return 1;
  case WM_PAINT: {
    PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
    //  깜빡이지 않게 메모리에 그린 뒤 한 번에
    RECT r; GetClientRect(h, &r);
    HDC mdc = CreateCompatibleDC(dc);
    HBITMAP mb = CreateCompatibleBitmap(dc, r.right, r.bottom);
    HGDIOBJ ob = SelectObject(mdc, mb);
    if (p) paint(p, mdc);
    BitBlt(dc, 0, 0, r.right, r.bottom, mdc, 0, 0, SRCCOPY);
    SelectObject(mdc, ob); DeleteObject(mb); DeleteDC(mdc);
    EndPaint(h, &ps);
    return 0;
  }
  case WM_PRINTCLIENT: if (p) paint(p, (HDC)w); return 0;
  case WM_SIZE: if (p && p->pages) { layout(p); InvalidateRect(h, NULL, FALSE); } return 0;
  case WM_MOUSEWHEEL: if (p) scrollTo(p, p->scroll - GET_WHEEL_DELTA_WPARAM(w) * 120 / WHEEL_DELTA); return 0;
  case WM_VSCROLL: if (p) {
      SCROLLINFO si = { sizeof si, SIF_ALL }; GetScrollInfo(h, SB_VERT, &si);
      RECT r; GetClientRect(h, &r);
      int y = p->scroll;
      switch (LOWORD(w)) {
      case SB_LINEUP: y -= 60; break; case SB_LINEDOWN: y += 60; break;
      case SB_PAGEUP: y -= r.bottom - 40; break; case SB_PAGEDOWN: y += r.bottom - 40; break;
      case SB_THUMBTRACK: case SB_THUMBPOSITION: y = si.nTrackPos; break;
      case SB_TOP: y = 0; break; case SB_BOTTOM: y = p->total; break;
      }
      scrollTo(p, y);
    } return 0;
  case WM_KEYDOWN: if (p) {
      RECT r; GetClientRect(h, &r);
      if (w == VK_DOWN) scrollTo(p, p->scroll + 60); else if (w == VK_UP) scrollTo(p, p->scroll - 60);
      else if (w == VK_NEXT || w == VK_SPACE) scrollTo(p, p->scroll + r.bottom - 40); else if (w == VK_PRIOR) scrollTo(p, p->scroll - r.bottom + 40);
      else if (w == VK_HOME) scrollTo(p, 0); else if (w == VK_END) scrollTo(p, p->total);
    } return 0;
  case WM_LBUTTONDOWN: SetFocus(h); return 0;
  case WM_LBUTTONDBLCLK: return 0;
  }
  return DefWindowProcW(h, m, w, l);
}

//  IUnknown 공통
static HRESULT pvQI(Preview *p, REFIID riid, void **ppv) {
  if (IsEqualIID(riid, &IID_IUnknown) || IsEqualIID(riid, &IID_IPreviewHandler)) *ppv = &p->vPrev;
  else if (IsEqualIID(riid, &IID_IInitializeWithStream)) *ppv = &p->vInit;
  else if (IsEqualIID(riid, &IID_IObjectWithSite)) *ppv = &p->vSite;
  else if (IsEqualIID(riid, &IID_IOleWindow)) *ppv = &p->vWin;
  else if (IsEqualIID(riid, &IID_IPreviewHandlerVisuals)) *ppv = &p->vVis;
  else { *ppv = NULL; return E_NOINTERFACE; }
  InterlockedIncrement(&p->ref);
  return S_OK;
}
static ULONG pvAddRef(Preview *p) { return InterlockedIncrement(&p->ref); }
static ULONG pvRelease(Preview *p) {
  LONG r = InterlockedDecrement(&p->ref);
  if (!r) {
    if (p->hwnd) DestroyWindow(p->hwnd);
    freeDoc(p);
    if (p->data) HeapFree(GetProcessHeap(), 0, p->data);
    if (p->site) IUnknown_Release(p->site);
    HeapFree(GetProcessHeap(), 0, p);
    InterlockedDecrement(&g_objs);
  }
  return r;
}
//  ⚠ 이름 앞에 u_ — COBJMACROS 가 IPreviewHandler_AddRef 같은 이름을 이미 쓴다
#define UNK(IF, field) \
  static HRESULT STDMETHODCALLTYPE u_##IF##_QI(IF *t, REFIID r, void **v) { return pvQI(FROM(Preview, field, t), r, v); } \
  static ULONG STDMETHODCALLTYPE u_##IF##_AddRef(IF *t) { return pvAddRef(FROM(Preview, field, t)); } \
  static ULONG STDMETHODCALLTYPE u_##IF##_Release(IF *t) { return pvRelease(FROM(Preview, field, t)); }
UNK(IPreviewHandler, vPrev)
UNK(IInitializeWithStream, vInit)
UNK(IObjectWithSite, vSite)
UNK(IOleWindow, vWin)
UNK(IPreviewHandlerVisuals, vVis)

//  IPreviewHandler
static HRESULT STDMETHODCALLTYPE PH_SetWindow(IPreviewHandler *t, HWND hwnd, const RECT *prc) {
  Preview *p = FROM(Preview, vPrev, t);
  p->parent = hwnd; if (prc) p->rc = *prc;
  if (p->hwnd) { SetParent(p->hwnd, hwnd); SetWindowPos(p->hwnd, NULL, p->rc.left, p->rc.top, p->rc.right - p->rc.left, p->rc.bottom - p->rc.top, SWP_NOZORDER | SWP_NOACTIVATE); }
  return S_OK;
}
static HRESULT STDMETHODCALLTYPE PH_SetRect(IPreviewHandler *t, const RECT *prc) {
  Preview *p = FROM(Preview, vPrev, t);
  if (!prc) return E_INVALIDARG;
  p->rc = *prc;
  if (p->hwnd) SetWindowPos(p->hwnd, NULL, p->rc.left, p->rc.top, p->rc.right - p->rc.left, p->rc.bottom - p->rc.top, SWP_NOZORDER | SWP_NOACTIVATE);
  return S_OK;
}
static HRESULT STDMETHODCALLTYPE PH_DoPreview(IPreviewHandler *t) {
  Preview *p = FROM(Preview, vPrev, t);
  if (!p->parent) return E_FAIL;
  if (!p->hwnd) {
    WNDCLASSW wc = { CS_DBLCLKS, wndProc, 0, 0, g_inst, NULL, LoadCursor(NULL, IDC_ARROW), NULL, NULL, WNDCLASS_NAME };
    RegisterClassW(&wc);
    p->hwnd = CreateWindowExW(0, WNDCLASS_NAME, L"", WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_CLIPSIBLINGS | WS_TABSTOP,
      p->rc.left, p->rc.top, p->rc.right - p->rc.left, p->rc.bottom - p->rc.top, p->parent, NULL, g_inst, p);
    if (!p->hwnd) return HRESULT_FROM_WIN32(GetLastError());
  }
  if (!pdfium()) p->err = -1;
  else if (!p->doc && p->data) {
    EnterCriticalSection(&g_lock);
    p->doc = P.LoadMemDocument(p->data, (int)p->size, NULL);
    if (!p->doc) p->err = (int)P.GetLastError(); else p->pages = P.GetPageCount(p->doc);
    if (p->doc && p->pages > 0) {
      p->pw = HeapAlloc(GetProcessHeap(), 0, sizeof(double) * p->pages);
      p->ph = HeapAlloc(GetProcessHeap(), 0, sizeof(double) * p->pages);
      p->top = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(int) * p->pages);
      p->cache = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(FPDF_BITMAP) * p->pages);
      p->cacheW = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(int) * p->pages);
      for (int i = 0; i < p->pages; i++) {
        if (!P.GetPageSizeByIndex(p->doc, i, &p->pw[i], &p->ph[i]) || p->pw[i] < 1 || p->ph[i] < 1) { p->pw[i] = 595; p->ph[i] = 842; }
      }
    } else if (p->doc && !p->err) p->err = 3;
    LeaveCriticalSection(&g_lock);
    if (p->pages) layout(p);
  }
  InvalidateRect(p->hwnd, NULL, TRUE);
  return S_OK;
}
static HRESULT STDMETHODCALLTYPE PH_Unload(IPreviewHandler *t) {
  Preview *p = FROM(Preview, vPrev, t);
  if (p->hwnd) { DestroyWindow(p->hwnd); p->hwnd = NULL; }
  freeDoc(p);
  if (p->data) { HeapFree(GetProcessHeap(), 0, p->data); p->data = NULL; }
  p->err = 0; p->scroll = 0; p->width = 0;
  return S_OK;
}
static HRESULT STDMETHODCALLTYPE PH_SetFocus(IPreviewHandler *t) { Preview *p = FROM(Preview, vPrev, t); if (p->hwnd) SetFocus(p->hwnd); return S_OK; }
static HRESULT STDMETHODCALLTYPE PH_QueryFocus(IPreviewHandler *t, HWND *phwnd) { (void)t; *phwnd = GetFocus(); return *phwnd ? S_OK : S_FALSE; }
static HRESULT STDMETHODCALLTYPE PH_TranslateAccelerator(IPreviewHandler *t, MSG *msg) {
  Preview *p = FROM(Preview, vPrev, t);
  IPreviewHandlerFrame *fr = NULL;
  HRESULT hr = S_FALSE;
  if (p->site && SUCCEEDED(IUnknown_QueryInterface(p->site, &IID_IPreviewHandlerFrame, (void **)&fr))) { hr = IPreviewHandlerFrame_TranslateAccelerator(fr, msg); IPreviewHandlerFrame_Release(fr); }
  return hr;
}
static IPreviewHandlerVtbl vtPrev = { u_IPreviewHandler_QI, u_IPreviewHandler_AddRef, u_IPreviewHandler_Release,
  PH_SetWindow, PH_SetRect, PH_DoPreview, PH_Unload, PH_SetFocus, PH_QueryFocus, PH_TranslateAccelerator };

//  IInitializeWithStream
static HRESULT STDMETHODCALLTYPE IS_Initialize(IInitializeWithStream *t, IStream *s, DWORD mode) {
  (void)mode;
  Preview *p = FROM(Preview, vInit, t);
  if (p->data) return HRESULT_FROM_WIN32(ERROR_ALREADY_INITIALIZED);
  return readStream(s, &p->data, &p->size);
}
static IInitializeWithStreamVtbl vtInit = { u_IInitializeWithStream_QI, u_IInitializeWithStream_AddRef, u_IInitializeWithStream_Release, IS_Initialize };

//  IObjectWithSite
static HRESULT STDMETHODCALLTYPE OS_SetSite(IObjectWithSite *t, IUnknown *site) {
  Preview *p = FROM(Preview, vSite, t);
  if (p->site) IUnknown_Release(p->site);
  p->site = site; if (site) IUnknown_AddRef(site);
  return S_OK;
}
static HRESULT STDMETHODCALLTYPE OS_GetSite(IObjectWithSite *t, REFIID r, void **v) {
  Preview *p = FROM(Preview, vSite, t);
  if (!p->site) { *v = NULL; return E_FAIL; }
  return IUnknown_QueryInterface(p->site, r, v);
}
static IObjectWithSiteVtbl vtSite = { u_IObjectWithSite_QI, u_IObjectWithSite_AddRef, u_IObjectWithSite_Release, OS_SetSite, OS_GetSite };

//  IOleWindow
static HRESULT STDMETHODCALLTYPE OW_GetWindow(IOleWindow *t, HWND *ph) { Preview *p = FROM(Preview, vWin, t); *ph = p->hwnd; return p->hwnd ? S_OK : E_FAIL; }
static HRESULT STDMETHODCALLTYPE OW_Ctx(IOleWindow *t, BOOL b) { (void)t; (void)b; return E_NOTIMPL; }
static IOleWindowVtbl vtWin = { u_IOleWindow_QI, u_IOleWindow_AddRef, u_IOleWindow_Release, OW_GetWindow, OW_Ctx };

//  IPreviewHandlerVisuals — 탐색기의 바탕색(어두운 모드)에 맞춘다
static HRESULT STDMETHODCALLTYPE PV_Bg(IPreviewHandlerVisuals *t, COLORREF c) { Preview *p = FROM(Preview, vVis, t); p->bg = c; if (p->hwnd) InvalidateRect(p->hwnd, NULL, FALSE); return S_OK; }
static HRESULT STDMETHODCALLTYPE PV_Font(IPreviewHandlerVisuals *t, const LOGFONTW *f) { (void)t; (void)f; return S_OK; }
static HRESULT STDMETHODCALLTYPE PV_Fg(IPreviewHandlerVisuals *t, COLORREF c) { Preview *p = FROM(Preview, vVis, t); p->fg = c; return S_OK; }
static IPreviewHandlerVisualsVtbl vtVis = { u_IPreviewHandlerVisuals_QI, u_IPreviewHandlerVisuals_AddRef, u_IPreviewHandlerVisuals_Release, PV_Bg, PV_Font, PV_Fg };

static HRESULT newPreview(REFIID riid, void **ppv) {
  Preview *p = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof *p);
  if (!p) return E_OUTOFMEMORY;
  p->vPrev = &vtPrev; p->vInit = &vtInit; p->vSite = &vtSite; p->vWin = &vtWin; p->vVis = &vtVis;
  p->ref = 1; p->bg = RGB(160, 160, 160); p->fg = RGB(40, 40, 40);
  InterlockedIncrement(&g_objs);
  HRESULT hr = pvQI(p, riid, ppv);
  pvRelease(p);
  return hr;
}

// ───────────── 미리 보기 그림(썸네일) ─────────────
typedef struct Thumb {
  IThumbnailProviderVtbl *vThumb;
  IInitializeWithStreamVtbl *vInit;
  LONG ref;
  BYTE *data; DWORD size;
} Thumb;
static HRESULT thQI(Thumb *p, REFIID riid, void **ppv) {
  if (IsEqualIID(riid, &IID_IUnknown) || IsEqualIID(riid, &IID_IThumbnailProvider)) *ppv = &p->vThumb;
  else if (IsEqualIID(riid, &IID_IInitializeWithStream)) *ppv = &p->vInit;
  else { *ppv = NULL; return E_NOINTERFACE; }
  InterlockedIncrement(&p->ref);
  return S_OK;
}
static ULONG thRelease(Thumb *p) {
  LONG r = InterlockedDecrement(&p->ref);
  if (!r) { if (p->data) HeapFree(GetProcessHeap(), 0, p->data); HeapFree(GetProcessHeap(), 0, p); InterlockedDecrement(&g_objs); }
  return r;
}
static HRESULT STDMETHODCALLTYPE TP_QI(IThumbnailProvider *t, REFIID r, void **v) { return thQI(FROM(Thumb, vThumb, t), r, v); }
static ULONG STDMETHODCALLTYPE TP_AddRef(IThumbnailProvider *t) { return InterlockedIncrement(&FROM(Thumb, vThumb, t)->ref); }
static ULONG STDMETHODCALLTYPE TP_Release(IThumbnailProvider *t) { return thRelease(FROM(Thumb, vThumb, t)); }
static HRESULT STDMETHODCALLTYPE TI_QI(IInitializeWithStream *t, REFIID r, void **v) { return thQI(FROM(Thumb, vInit, t), r, v); }
static ULONG STDMETHODCALLTYPE TI_AddRef(IInitializeWithStream *t) { return InterlockedIncrement(&FROM(Thumb, vInit, t)->ref); }
static ULONG STDMETHODCALLTYPE TI_Release(IInitializeWithStream *t) { return thRelease(FROM(Thumb, vInit, t)); }
static HRESULT STDMETHODCALLTYPE TI_Initialize(IInitializeWithStream *t, IStream *s, DWORD mode) {
  (void)mode;
  Thumb *p = FROM(Thumb, vInit, t);
  if (p->data) return HRESULT_FROM_WIN32(ERROR_ALREADY_INITIALIZED);
  return readStream(s, &p->data, &p->size);
}
static HRESULT STDMETHODCALLTYPE TP_GetThumbnail(IThumbnailProvider *t, UINT cx, HBITMAP *phbmp, WTS_ALPHATYPE *pa) {
  Thumb *p = FROM(Thumb, vThumb, t);
  if (!p->data) return E_UNEXPECTED;
  if (!pdfium()) return E_FAIL;
  HRESULT hr = E_FAIL;
  EnterCriticalSection(&g_lock);
  FPDF_DOCUMENT doc = P.LoadMemDocument(p->data, (int)p->size, NULL);
  if (doc) {
    double w = 0, h = 0;
    if (P.GetPageCount(doc) > 0 && P.GetPageSizeByIndex(doc, 0, &w, &h) && w > 0 && h > 0) {
      int W = w >= h ? (int)cx : (int)(cx * w / h), H = h >= w ? (int)cx : (int)(cx * h / w);
      if (W < 1) W = 1; if (H < 1) H = 1;
      FPDF_BITMAP bm = renderPage(doc, 0, W, H);
      if (bm) {
        BITMAPINFO bi = { { sizeof(BITMAPINFOHEADER), W, -H, 1, 32, BI_RGB } };
        BYTE *bits = NULL;
        HBITMAP hb = CreateDIBSection(NULL, &bi, DIB_RGB_COLORS, (void **)&bits, NULL, 0);
        if (hb) {
          BYTE *src = P.BitmapGetBuffer(bm);
          int stride = P.BitmapGetStride(bm);
          for (int y = 0; y < H; y++) {
            BYTE *d = bits + y * W * 4, *s = src + y * stride;
            for (int x = 0; x < W; x++) { d[x * 4] = s[x * 4]; d[x * 4 + 1] = s[x * 4 + 1]; d[x * 4 + 2] = s[x * 4 + 2]; d[x * 4 + 3] = 255; }
          }
          *phbmp = hb; *pa = WTSAT_RGB; hr = S_OK;
        }
        P.BitmapDestroy(bm);
      }
    }
    P.CloseDocument(doc);
  }
  LeaveCriticalSection(&g_lock);
  return hr;
}
static IThumbnailProviderVtbl vtThumb = { TP_QI, TP_AddRef, TP_Release, TP_GetThumbnail };
static IInitializeWithStreamVtbl vtThumbInit = { TI_QI, TI_AddRef, TI_Release, TI_Initialize };
static HRESULT newThumb(REFIID riid, void **ppv) {
  Thumb *p = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof *p);
  if (!p) return E_OUTOFMEMORY;
  p->vThumb = &vtThumb; p->vInit = &vtThumbInit; p->ref = 1;
  InterlockedIncrement(&g_objs);
  HRESULT hr = thQI(p, riid, ppv);
  thRelease(p);
  return hr;
}

// ───────────── 클래스 공장 ─────────────
typedef struct { IClassFactoryVtbl *v; HRESULT (*make)(REFIID, void **); } Factory;
static HRESULT STDMETHODCALLTYPE CF_QI(IClassFactory *t, REFIID r, void **v) {
  if (IsEqualIID(r, &IID_IUnknown) || IsEqualIID(r, &IID_IClassFactory)) { *v = t; InterlockedIncrement(&g_locks); return S_OK; }
  *v = NULL; return E_NOINTERFACE;
}
static ULONG STDMETHODCALLTYPE CF_AddRef(IClassFactory *t) { (void)t; InterlockedIncrement(&g_locks); return 2; }
static ULONG STDMETHODCALLTYPE CF_Release(IClassFactory *t) { (void)t; InterlockedDecrement(&g_locks); return 1; }
static HRESULT STDMETHODCALLTYPE CF_Create(IClassFactory *t, IUnknown *outer, REFIID r, void **v) {
  if (outer) return CLASS_E_NOAGGREGATION;
  return ((Factory *)t)->make(r, v);
}
static HRESULT STDMETHODCALLTYPE CF_Lock(IClassFactory *t, BOOL lock) { (void)t; if (lock) InterlockedIncrement(&g_locks); else InterlockedDecrement(&g_locks); return S_OK; }
static IClassFactoryVtbl vtCF = { CF_QI, CF_AddRef, CF_Release, CF_Create, CF_Lock };
static Factory fPreview = { &vtCF, newPreview }, fThumb = { &vtCF, newThumb };

HRESULT STDAPICALLTYPE DllGetClassObject(REFCLSID clsid, REFIID riid, void **ppv) {
  Factory *f = IsEqualCLSID(clsid, &CLSID_HanilPreview) ? &fPreview : IsEqualCLSID(clsid, &CLSID_HanilThumb) ? &fThumb : NULL;
  if (!f) { *ppv = NULL; return CLASS_E_CLASSNOTAVAILABLE; }
  return CF_QI((IClassFactory *)f, riid, ppv);
}
HRESULT STDAPICALLTYPE DllCanUnloadNow(void) { return g_objs == 0 && g_locks == 0 ? S_OK : S_FALSE; }

// ───────────── 등록(HKCU) ─────────────
static LONG setStr(const WCHAR *key, const WCHAR *name, const WCHAR *val) {
  HKEY k;
  LONG r = RegCreateKeyExW(HKEY_CURRENT_USER, key, 0, NULL, 0, KEY_WRITE, NULL, &k, NULL);
  if (r) return r;
  r = RegSetValueExW(k, name, 0, REG_SZ, (const BYTE *)val, (lstrlenW(val) + 1) * sizeof(WCHAR));
  RegCloseKey(k);
  return r;
}
static LONG setDword(const WCHAR *key, const WCHAR *name, DWORD v) {
  HKEY k;
  LONG r = RegCreateKeyExW(HKEY_CURRENT_USER, key, 0, NULL, 0, KEY_WRITE, NULL, &k, NULL);
  if (r) return r;
  r = RegSetValueExW(k, name, 0, REG_DWORD, (const BYTE *)&v, sizeof v);
  RegCloseKey(k);
  return r;
}
#define CLS L"Software\\Classes\\CLSID\\"
HRESULT STDAPICALLTYPE DllRegisterServer(void) {
  WCHAR dll[MAX_PATH];
  GetModuleFileNameW(g_inst, dll, MAX_PATH);
  LONG r = 0;
  r |= setStr(CLS S_PREVIEW, NULL, L"한일 PDF 리더 미리 보기");
  r |= setStr(CLS S_PREVIEW, L"DisplayName", L"한일 PDF 리더 미리 보기");
  r |= setStr(CLS S_PREVIEW, L"AppID", S_PREVHOST_APPID);
  r |= setDword(CLS S_PREVIEW, L"DisableLowILProcessIsolation", 1);
  r |= setStr(CLS S_PREVIEW L"\\InprocServer32", NULL, dll);
  r |= setStr(CLS S_PREVIEW L"\\InprocServer32", L"ThreadingModel", L"Apartment");
  r |= setStr(CLS S_THUMB, NULL, L"한일 PDF 리더 미리 보기 그림");
  r |= setStr(CLS S_THUMB L"\\InprocServer32", NULL, dll);
  r |= setStr(CLS S_THUMB L"\\InprocServer32", L"ThreadingModel", L"Apartment");
  r |= setStr(L"Software\\Classes\\.pdf\\shellex\\" S_IPREVIEW, NULL, S_PREVIEW);
  r |= setStr(L"Software\\Classes\\.pdf\\shellex\\" S_ITHUMB, NULL, S_THUMB);
  r |= setStr(L"Software\\Classes\\HanilPDF.Document\\shellex\\" S_IPREVIEW, NULL, S_PREVIEW);
  r |= setStr(L"Software\\Classes\\HanilPDF.Document\\shellex\\" S_ITHUMB, NULL, S_THUMB);
  r |= setStr(L"Software\\Microsoft\\Windows\\CurrentVersion\\PreviewHandlers", S_PREVIEW, L"한일 PDF 리더 미리 보기");
  SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, NULL, NULL);
  return r ? E_FAIL : S_OK;
}
HRESULT STDAPICALLTYPE DllUnregisterServer(void) {
  RegDeleteTreeW(HKEY_CURRENT_USER, CLS S_PREVIEW);
  RegDeleteTreeW(HKEY_CURRENT_USER, CLS S_THUMB);
  RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\.pdf\\shellex\\" S_IPREVIEW);
  RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\.pdf\\shellex\\" S_ITHUMB);
  RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\HanilPDF.Document\\shellex\\" S_IPREVIEW);
  RegDeleteTreeW(HKEY_CURRENT_USER, L"Software\\Classes\\HanilPDF.Document\\shellex\\" S_ITHUMB);
  HKEY k;
  if (!RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\PreviewHandlers", 0, KEY_WRITE, &k)) { RegDeleteValueW(k, S_PREVIEW); RegCloseKey(k); }
  SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, NULL, NULL);
  return S_OK;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD why, LPVOID r) {
  (void)r;
  if (why == DLL_PROCESS_ATTACH) { g_inst = h; DisableThreadLibraryCalls(h); InitializeCriticalSection(&g_lock); }
  return TRUE;
}
