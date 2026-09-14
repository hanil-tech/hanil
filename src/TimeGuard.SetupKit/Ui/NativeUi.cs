using System.Runtime.InteropServices;
using System.Text;

namespace Hanil.TimeGuard.SetupKit.Ui;

internal delegate IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

/// <summary>
/// 설치 화면을 그리는 데 필요한 Win32 API.
///
/// WinForms/WPF 를 쓰지 않고 표준 Windows 컨트롤을 직접 만든다.
/// 그래서 대상 PC 에 .NET 데스크톱 런타임을 따로 깔 필요가 없고,
/// 설치 프로그램 자체도 몇백 KB 로 끝난다.
/// </summary>
internal static class NativeUi
{
    // ---- 메시지 ----
    internal const uint WM_CREATE = 0x0001;
    internal const uint WM_DESTROY = 0x0002;
    internal const uint WM_CLOSE = 0x0010;
    internal const uint WM_PAINT = 0x000F;
    internal const uint WM_COMMAND = 0x0111;
    internal const uint WM_CTLCOLORSTATIC = 0x0138;
    internal const uint WM_CTLCOLORBTN = 0x0135;
    internal const uint WM_SETFONT = 0x0030;
    internal const uint WM_APP = 0x8000;
    internal const uint WM_SETICON = 0x0080;

    /// <summary>작업 스레드가 진행 상황을 알릴 때 쓴다.</summary>
    internal const uint WM_SETUP_PROGRESS = WM_APP + 1;

    /// <summary>작업 스레드가 끝났음을 알릴 때 쓴다.</summary>
    internal const uint WM_SETUP_FINISHED = WM_APP + 2;

    // ---- 창 스타일 ----
    internal const uint WS_OVERLAPPED = 0x00000000;
    internal const uint WS_CAPTION = 0x00C00000;
    internal const uint WS_SYSMENU = 0x00080000;
    internal const uint WS_MINIMIZEBOX = 0x00020000;
    internal const uint WS_CHILD = 0x40000000;
    internal const uint WS_VISIBLE = 0x10000000;
    internal const uint WS_TABSTOP = 0x00010000;
    internal const uint WS_VSCROLL = 0x00200000;
    internal const uint WS_GROUP = 0x00020000;

    internal const uint WS_EX_CLIENTEDGE = 0x00000200;
    internal const uint WS_EX_CONTROLPARENT = 0x00010000;

    // ---- 컨트롤 스타일 ----
    internal const uint SS_LEFT = 0x00000000;
    internal const uint SS_ETCHEDHORZ = 0x00000010;
    internal const uint SS_NOPREFIX = 0x00000080;

    internal const uint BS_PUSHBUTTON = 0x00000000;
    internal const uint BS_DEFPUSHBUTTON = 0x00000001;
    internal const uint BS_AUTOCHECKBOX = 0x00000003;
    internal const uint BS_MULTILINE = 0x00002000;

    internal const uint ES_MULTILINE = 0x0004;
    internal const uint ES_AUTOVSCROLL = 0x0040;
    internal const uint ES_NUMBER = 0x2000;
    internal const uint ES_READONLY = 0x0800;

    internal const uint BM_GETCHECK = 0x00F0;
    internal const uint BM_SETCHECK = 0x00F1;

    internal const uint EM_SETSEL = 0x00B1;
    internal const uint EM_REPLACESEL = 0x00C2;
    internal const uint EM_SCROLLCARET = 0x00B7;

    // ---- 진행 막대 (공용 컨트롤) ----
    internal const string ProgressClass = "msctls_progress32";

    internal const uint PBS_MARQUEE = 0x08;
    internal const uint PBM_SETRANGE32 = 0x0406;
    internal const uint PBM_SETPOS = 0x0402;
    internal const uint PBM_SETMARQUEE = 0x040A;

    internal const int SW_HIDE = 0;
    internal const int SW_SHOW = 5;
    internal const int SW_SHOWNORMAL = 1;

    internal const int SM_CXSCREEN = 0;
    internal const int SM_CYSCREEN = 1;

    internal const int IDCANCEL = 2;

    internal const int TRANSPARENT = 1;
    internal const int OPAQUE = 2;

    internal const int FW_NORMAL = 400;
    internal const int FW_SEMIBOLD = 600;
    internal const int FW_BOLD = 700;

    internal const uint HANGEUL_CHARSET = 129;
    internal const uint CLEARTYPE_QUALITY = 5;

    internal static readonly IntPtr IDI_APPLICATION = new(32512);
    internal static readonly IntPtr IDC_ARROW = new(32512);

    /// <summary>COLORREF 는 0x00BBGGRR 순서다.</summary>
    internal static uint Rgb(byte r, byte g, byte b) => (uint)(r | (g << 8) | (b << 16));

    // ---- 구조체 ----

    [StructLayout(LayoutKind.Sequential)]
    internal struct POINT { public int X; public int Y; }

    [StructLayout(LayoutKind.Sequential)]
    internal struct RECT
    {
        public int Left, Top, Right, Bottom;
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

    [StructLayout(LayoutKind.Sequential)]
    internal struct INITCOMMONCONTROLSEX
    {
        public uint dwSize;
        public uint dwICC;
    }

    internal const uint ICC_PROGRESS_CLASS = 0x00000020;
    internal const uint ICC_STANDARD_CLASSES = 0x00004000;

    // ---- 창 ----

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
    internal static extern bool EnableWindow(IntPtr hWnd, bool enable);

    [DllImport("user32.dll")]
    internal static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern IntPtr SetFocus(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern int GetSystemMetrics(int index);

    [DllImport("user32.dll")]
    internal static extern bool AdjustWindowRect(ref RECT rect, uint style, bool menu);

    [DllImport("user32.dll")]
    internal static extern void PostQuitMessage(int exitCode);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetMessageW(out MSG message, IntPtr hWnd, uint filterMin, uint filterMax);

    [DllImport("user32.dll")]
    internal static extern bool TranslateMessage(ref MSG message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr DispatchMessageW(ref MSG message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern bool IsDialogMessageW(IntPtr dialog, ref MSG message);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessageW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr SendMessageW(IntPtr hWnd, uint msg, IntPtr wParam, string lParam);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    internal static extern bool PostMessageW(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern bool SetWindowTextW(IntPtr hWnd, string text);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int maxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int GetWindowTextLengthW(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    internal const uint MB_OK = 0x0;
    internal const uint MB_YESNO = 0x4;
    internal const uint MB_ICONINFORMATION = 0x40;
    internal const uint MB_ICONWARNING = 0x30;
    internal const uint MB_ICONERROR = 0x10;
    internal const uint MB_DEFBUTTON2 = 0x100;
    internal const int IDYES = 6;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr GetModuleHandleW(string? moduleName);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr LoadIconW(IntPtr instance, IntPtr iconName);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr LoadCursorW(IntPtr instance, IntPtr cursorName);

    [DllImport("comctl32.dll")]
    internal static extern bool InitCommonControlsEx(ref INITCOMMONCONTROLSEX controls);

    // ---- 그리기 ----

    [DllImport("user32.dll")]
    internal static extern IntPtr BeginPaint(IntPtr hWnd, out PAINTSTRUCT paint);

    [DllImport("user32.dll")]
    internal static extern bool EndPaint(IntPtr hWnd, ref PAINTSTRUCT paint);

    [DllImport("user32.dll")]
    internal static extern bool GetClientRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    internal static extern int FillRect(IntPtr hdc, ref RECT rect, IntPtr brush);

    [DllImport("gdi32.dll")]
    internal static extern IntPtr CreateSolidBrush(uint color);

    [DllImport("gdi32.dll")]
    internal static extern bool DeleteObject(IntPtr obj);

    [DllImport("gdi32.dll")]
    internal static extern uint SetTextColor(IntPtr hdc, uint color);

    [DllImport("gdi32.dll")]
    internal static extern uint SetBkColor(IntPtr hdc, uint color);

    [DllImport("gdi32.dll")]
    internal static extern int SetBkMode(IntPtr hdc, int mode);

    [DllImport("gdi32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr CreateFontW(
        int height, int width, int escapement, int orientation, int weight,
        uint italic, uint underline, uint strikeOut, uint charSet,
        uint outputPrecision, uint clipPrecision, uint quality, uint pitchAndFamily,
        string faceName);

    // ---- 클립보드 ----

    [DllImport("user32.dll")]
    internal static extern bool OpenClipboard(IntPtr hWnd);

    [DllImport("user32.dll")]
    internal static extern bool EmptyClipboard();

    [DllImport("user32.dll")]
    internal static extern IntPtr SetClipboardData(uint format, IntPtr data);

    [DllImport("user32.dll")]
    internal static extern bool CloseClipboard();

    [DllImport("kernel32.dll")]
    internal static extern IntPtr GlobalAlloc(uint flags, UIntPtr bytes);

    [DllImport("kernel32.dll")]
    internal static extern IntPtr GlobalLock(IntPtr handle);

    [DllImport("kernel32.dll")]
    internal static extern bool GlobalUnlock(IntPtr handle);

    internal const uint GMEM_MOVEABLE = 0x0002;
    internal const uint CF_UNICODETEXT = 13;

    /// <summary>글자를 클립보드에 넣는다. 실패해도 설치에는 지장이 없다.</summary>
    internal static bool CopyToClipboard(IntPtr owner, string text)
    {
        try
        {
            if (!OpenClipboard(owner)) return false;

            try
            {
                EmptyClipboard();

                var bytes = (UIntPtr)((text.Length + 1) * 2);
                var handle = GlobalAlloc(GMEM_MOVEABLE, bytes);
                if (handle == IntPtr.Zero) return false;

                var target = GlobalLock(handle);
                if (target == IntPtr.Zero) return false;

                try { Marshal.Copy(text.ToCharArray(), 0, target, text.Length); Marshal.WriteInt16(target, text.Length * 2, 0); }
                finally { GlobalUnlock(handle); }

                return SetClipboardData(CF_UNICODETEXT, handle) != IntPtr.Zero;
            }
            finally
            {
                CloseClipboard();
            }
        }
        catch (Exception)
        {
            return false;
        }
    }

    // ---- 바깥 프로그램 실행 (브라우저 열기) ----

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    internal static extern IntPtr ShellExecuteW(
        IntPtr hWnd, string? operation, string file, string? parameters, string? directory, int showCommand);
}
