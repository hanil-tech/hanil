using System.Runtime.InteropServices;

namespace Hanil.TimeGuard.Agent.Interop;

internal delegate IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

/// <summary>
/// 경고 창과 트레이 아이콘을 그리는 데 필요한 Win32 API.
/// WinForms/WPF 없이 동작하도록 필요한 것만 직접 선언했다.
/// </summary>
internal static class Win32
{
    // ---- 메시지 ----
    internal const uint WM_DESTROY = 0x0002;
    internal const uint WM_PAINT = 0x000F;
    internal const uint WM_CLOSE = 0x0010;
    internal const uint WM_QUIT = 0x0012;
    internal const uint WM_ERASEBKGND = 0x0014;
    internal const uint WM_TIMER = 0x0113;
    internal const uint WM_COMMAND = 0x0111;
    internal const uint WM_DISPLAYCHANGE = 0x007E;
    internal const uint WM_DPICHANGED = 0x02E0;
    internal const uint WM_APP = 0x8000;
    internal const uint WM_TRAYICON = WM_APP + 1;
    internal const uint WM_USER = 0x0400;
    internal const uint WM_LBUTTONUP = 0x0202;
    internal const uint WM_RBUTTONUP = 0x0205;
    internal const uint WM_CONTEXTMENU = 0x007B;

    /// <summary>탐색기가 다시 시작되면 트레이 아이콘을 다시 등록해야 한다.</summary>
    internal const string TaskbarCreatedMessage = "TaskbarCreated";

    // ---- 윈도우 스타일 ----
    internal const uint WS_POPUP = 0x80000000;
    internal const uint WS_VISIBLE = 0x10000000;
    internal const uint WS_BORDER = 0x00800000;
    internal const uint WS_EX_TOPMOST = 0x00000008;
    internal const uint WS_EX_TOOLWINDOW = 0x00000080;
    internal const uint WS_EX_NOACTIVATE = 0x08000000;

    internal const int SW_HIDE = 0;
    internal const int SW_SHOWNOACTIVATE = 4;

    internal static readonly IntPtr HWND_TOPMOST = new(-1);
    internal static readonly IntPtr HWND_MESSAGE = new(-3);

    internal const uint SWP_NOSIZE = 0x0001;
    internal const uint SWP_NOMOVE = 0x0002;
    internal const uint SWP_NOACTIVATE = 0x0010;
    internal const uint SWP_SHOWWINDOW = 0x0040;

    internal const int SM_CXSCREEN = 0;
    internal const int SM_CYSCREEN = 1;

    // ---- 구조체 ----

    [StructLayout(LayoutKind.Sequential)]
    internal struct POINT
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;

        public int Width => Right - Left;
        public int Height => Bottom - Top;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct MSG
    {
        public IntPtr hwnd;
        public uint message;
        public IntPtr wParam;
        public IntPtr lParam;
        public uint time;
        public POINT pt;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct WNDCLASSEX
    {
        public uint cbSize;
        public uint style;
        public IntPtr lpfnWndProc;
        public int cbClsExtra;
        public int cbWndExtra;
        public IntPtr hInstance;
        public IntPtr hIcon;
        public IntPtr hCursor;
        public IntPtr hbrBackground;
        [MarshalAs(UnmanagedType.LPWStr)] public string? lpszMenuName;
        [MarshalAs(UnmanagedType.LPWStr)] public string lpszClassName;
        public IntPtr hIconSm;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct PAINTSTRUCT
    {
        public IntPtr hdc;
        public bool fErase;
        public RECT rcPaint;
        public bool fRestore;
        public bool fIncUpdate;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 32)] public byte[] rgbReserved;
    }

    // ---- 창 관리 ----

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    internal static extern ushort RegisterClassExW(ref WNDCLASSEX windowClass);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    internal static extern IntPtr CreateWindowExW(
        uint exStyle, string className, string? windowName, uint style,
        int x, int y, int width, int height,
        IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr DefWindowProcW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true)]
    internal static extern bool DestroyWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern bool ShowWindow(IntPtr hWnd, int command);

    [DllImport("user32.dll")]
    internal static extern bool SetWindowPos(
        IntPtr hWnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);

    [DllImport("user32.dll")]
    internal static extern bool InvalidateRect(IntPtr hWnd, IntPtr rect, bool erase);

    [DllImport("user32.dll")]
    internal static extern bool GetClientRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    internal static extern int GetSystemMetrics(int index);

    [DllImport("user32.dll")]
    internal static extern void PostQuitMessage(int exitCode);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetMessageW(out MSG message, IntPtr hWnd, uint filterMin, uint filterMax);

    [DllImport("user32.dll")]
    internal static extern bool TranslateMessage(ref MSG message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr DispatchMessageW(ref MSG message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern uint RegisterWindowMessageW(string message);

    [DllImport("user32.dll", SetLastError = true)]
    internal static extern IntPtr SetTimer(IntPtr hWnd, IntPtr eventId, uint elapseMs, IntPtr callback);

    [DllImport("user32.dll", SetLastError = true)]
    internal static extern bool KillTimer(IntPtr hWnd, IntPtr eventId);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr GetModuleHandleW(string? moduleName);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr LoadIconW(IntPtr instance, IntPtr iconName);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr LoadCursorW(IntPtr instance, IntPtr cursorName);

    internal static readonly IntPtr IDI_WARNING = new(32515);
    internal static readonly IntPtr IDI_INFORMATION = new(32516);
    internal static readonly IntPtr IDC_ARROW = new(32512);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    internal const uint MB_OK = 0x0;
    internal const uint MB_ICONINFORMATION = 0x40;
    internal const uint MB_TOPMOST = 0x40000;

    [DllImport("user32.dll")]
    internal static extern bool SetForegroundWindow(IntPtr hWnd);

    // ---- 그리기 ----

    [DllImport("user32.dll")]
    internal static extern IntPtr BeginPaint(IntPtr hWnd, out PAINTSTRUCT paint);

    [DllImport("user32.dll")]
    internal static extern bool EndPaint(IntPtr hWnd, ref PAINTSTRUCT paint);

    [DllImport("user32.dll")]
    internal static extern int FillRect(IntPtr hdc, ref RECT rect, IntPtr brush);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int DrawTextW(IntPtr hdc, string text, int count, ref RECT rect, uint format);

    internal const uint DT_CENTER = 0x00000001;
    internal const uint DT_VCENTER = 0x00000004;
    internal const uint DT_SINGLELINE = 0x00000020;
    internal const uint DT_WORDBREAK = 0x00000010;
    internal const uint DT_NOPREFIX = 0x00000800;

    [DllImport("gdi32.dll")]
    internal static extern IntPtr CreateSolidBrush(uint color);

    [DllImport("gdi32.dll")]
    internal static extern bool DeleteObject(IntPtr obj);

    [DllImport("gdi32.dll")]
    internal static extern IntPtr SelectObject(IntPtr hdc, IntPtr obj);

    [DllImport("gdi32.dll")]
    internal static extern uint SetTextColor(IntPtr hdc, uint color);

    [DllImport("gdi32.dll")]
    internal static extern int SetBkMode(IntPtr hdc, int mode);

    internal const int TRANSPARENT = 1;

    [DllImport("gdi32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr CreateFontW(
        int height, int width, int escapement, int orientation, int weight,
        uint italic, uint underline, uint strikeOut, uint charSet,
        uint outputPrecision, uint clipPrecision, uint quality, uint pitchAndFamily,
        string faceName);

    internal const uint HANGEUL_CHARSET = 129;
    internal const uint DEFAULT_CHARSET = 1;
    internal const int FW_NORMAL = 400;
    internal const int FW_BOLD = 700;
    internal const uint CLEARTYPE_QUALITY = 5;

    /// <summary>COLORREF 는 0x00BBGGRR 순서다.</summary>
    internal static uint Rgb(byte r, byte g, byte b) => (uint)(r | (g << 8) | (b << 16));

    // ---- 트레이 아이콘 ----

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct NOTIFYICONDATA
    {
        public uint cbSize;
        public IntPtr hWnd;
        public uint uID;
        public uint uFlags;
        public uint uCallbackMessage;
        public IntPtr hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string szTip;
        public uint dwState;
        public uint dwStateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szInfo;
        public uint uVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string szInfoTitle;
        public uint dwInfoFlags;
        public Guid guidItem;
        public IntPtr hBalloonIcon;
    }

    internal const uint NIM_ADD = 0x00000000;
    internal const uint NIM_MODIFY = 0x00000001;
    internal const uint NIM_DELETE = 0x00000002;

    internal const uint NIF_MESSAGE = 0x00000001;
    internal const uint NIF_ICON = 0x00000002;
    internal const uint NIF_TIP = 0x00000004;
    internal const uint NIF_INFO = 0x00000010;

    internal const uint NIIF_INFO = 0x00000001;
    internal const uint NIIF_WARNING = 0x00000002;
    internal const uint NIIF_ERROR = 0x00000003;

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    internal static extern bool Shell_NotifyIconW(uint message, ref NOTIFYICONDATA data);

    // ---- 팝업 메뉴 ----

    [DllImport("user32.dll")]
    internal static extern IntPtr CreatePopupMenu();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern bool AppendMenuW(IntPtr menu, uint flags, UIntPtr itemId, string? item);

    [DllImport("user32.dll")]
    internal static extern bool TrackPopupMenu(
        IntPtr menu, uint flags, int x, int y, int reserved, IntPtr hWnd, IntPtr rect);

    [DllImport("user32.dll")]
    internal static extern bool DestroyMenu(IntPtr menu);

    [DllImport("user32.dll")]
    internal static extern bool GetCursorPos(out POINT point);

    // ---- 대화 상자용 컨트롤 ----

    internal const uint WS_CHILD = 0x40000000;
    internal const uint WS_TABSTOP = 0x00010000;
    internal const uint WS_VSCROLL = 0x00200000;
    internal const uint WS_OVERLAPPED = 0x00000000;
    internal const uint WS_CAPTION = 0x00C00000;
    internal const uint WS_SYSMENU = 0x00080000;

    internal const uint ES_MULTILINE = 0x0004;
    internal const uint ES_AUTOVSCROLL = 0x0040;
    internal const uint ES_WANTRETURN = 0x1000;

    internal const uint CBS_DROPDOWNLIST = 0x0003;

    internal const uint BS_PUSHBUTTON = 0x0000;
    internal const uint BS_DEFPUSHBUTTON = 0x0001;

    internal const uint WM_SETFONT = 0x0030;
    internal const uint WM_GETTEXT = 0x000D;
    internal const uint WM_GETTEXTLENGTH = 0x000E;

    internal const uint CB_ADDSTRING = 0x0143;
    internal const uint CB_SETCURSEL = 0x014E;
    internal const uint CB_GETCURSEL = 0x0147;

    internal const uint SW_SHOW = 5;

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessageW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessageW(IntPtr hWnd, uint msg, IntPtr wParam, string lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetWindowTextW(IntPtr hWnd, System.Text.StringBuilder text, int maxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetWindowTextLengthW(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern bool EnableWindow(IntPtr hWnd, bool enable);

    [DllImport("user32.dll")]
    internal static extern IntPtr SetFocus(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern bool IsDialogMessageW(IntPtr dialog, ref MSG message);

    internal const uint MF_STRING = 0x00000000;
    internal const uint MF_SEPARATOR = 0x00000800;
    internal const uint MF_GRAYED = 0x00000001;
    internal const uint TPM_RIGHTBUTTON = 0x0002;
}
