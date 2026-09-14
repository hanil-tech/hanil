using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Schedule;
using Hanil.TimeGuard.Agent.Interop;
using static Hanil.TimeGuard.Agent.Interop.Win32;

namespace Hanil.TimeGuard.Agent;

/// <summary>
/// 트레이 아이콘과 경고 창을 담당한다.
/// WinForms 없이 Win32 창을 직접 만들어 쓰므로 배포에 추가 런타임이 필요 없다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class AgentWindow : IDisposable
{
    private const string WindowClassName = "HanilTimeGuardAgentWindow";
    private const uint TrayIconId = 1;
    private static readonly IntPtr TimerId = new(1);
    private const uint TimerIntervalMs = 1000;

    private const uint MenuShowStatus = 101;
    private const uint MenuShowRemaining = 102;

    private readonly StatusPoller _poller;
    private readonly WndProc _wndProcDelegate; // GC 가 수거하지 못하도록 필드로 붙잡아 둔다
    private readonly uint _taskbarCreatedMessage;

    private IntPtr _hwnd;
    private IntPtr _instance;
    private bool _trayIconAdded;
    private bool _countdownVisible;
    private bool _disposed;

    private long _lastNoticeId;
    private string _lastTip = string.Empty;

    // 화면에 그릴 내용. WM_PAINT 는 이 값만 읽는다.
    private string _titleText = string.Empty;
    private string _countdownText = string.Empty;
    private string _messageText = string.Empty;
    private string _footerText = string.Empty;

    public AgentWindow(StatusPoller poller)
    {
        _poller = poller;
        _wndProcDelegate = WindowProcedure;
        _taskbarCreatedMessage = RegisterWindowMessageW(TaskbarCreatedMessage);
    }

    /// <summary>창을 만들고 메시지 루프를 돈다. 루프가 끝나면 반환된다.</summary>
    public void Run()
    {
        _instance = GetModuleHandleW(null);

        var windowClass = new WNDCLASSEX
        {
            cbSize = (uint)Marshal.SizeOf<WNDCLASSEX>(),
            style = 0,
            lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_wndProcDelegate),
            hInstance = _instance,
            hIcon = LoadIconW(IntPtr.Zero, IDI_WARNING),
            hCursor = LoadCursorW(IntPtr.Zero, IDC_ARROW),
            hbrBackground = IntPtr.Zero, // 배경은 WM_PAINT 에서 직접 칠한다
            lpszClassName = WindowClassName
        };

        if (RegisterClassExW(ref windowClass) == 0)
        {
            var error = Marshal.GetLastWin32Error();
            // 이미 등록돼 있는 경우(1410)는 그대로 진행한다.
            if (error != 1410)
                throw new InvalidOperationException($"창 클래스를 등록하지 못했습니다. 오류 {error}");
        }

        var (width, height) = CalculateWindowSize();
        var x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
        var y = (int)((GetSystemMetrics(SM_CYSCREEN) - height) * 0.35);

        _hwnd = CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            WindowClassName,
            "한일 TimeGuard",
            WS_POPUP | WS_BORDER,
            x, y, width, height,
            IntPtr.Zero, IntPtr.Zero, _instance, IntPtr.Zero);

        if (_hwnd == IntPtr.Zero)
            throw new InvalidOperationException($"창을 만들지 못했습니다. 오류 {Marshal.GetLastWin32Error()}");

        AddTrayIcon();
        SetTimer(_hwnd, TimerId, TimerIntervalMs, IntPtr.Zero);

        while (GetMessageW(out var message, IntPtr.Zero, 0, 0) > 0)
        {
            TranslateMessage(ref message);
            DispatchMessageW(ref message);
        }
    }

    private static (int Width, int Height) CalculateWindowSize()
    {
        var screenWidth = GetSystemMetrics(SM_CXSCREEN);
        var screenHeight = GetSystemMetrics(SM_CYSCREEN);

        var width = Math.Clamp((int)(screenWidth * 0.42), 480, 860);
        var height = Math.Clamp((int)(width * 0.46), 240, 420);

        // 창이 화면을 넘지 않도록 한 번 더 제한한다.
        width = Math.Min(width, screenWidth - 40);
        height = Math.Min(height, screenHeight - 40);

        return (width, height);
    }

    private IntPtr WindowProcedure(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg == _taskbarCreatedMessage)
        {
            // 탐색기가 다시 시작되면 트레이 아이콘이 사라지므로 다시 등록한다.
            _trayIconAdded = false;
            AddTrayIcon();
            return IntPtr.Zero;
        }

        switch (msg)
        {
            case WM_TIMER:
                OnTick();
                return IntPtr.Zero;

            case WM_PAINT:
                OnPaint(hWnd);
                return IntPtr.Zero;

            case WM_ERASEBKGND:
                return new IntPtr(1); // 깜빡임을 줄이기 위해 배경 지우기를 막는다

            case WM_TRAYICON:
                OnTrayMessage((uint)(lParam.ToInt64() & 0xFFFF));
                return IntPtr.Zero;

            case WM_COMMAND:
                OnCommand((uint)(wParam.ToInt64() & 0xFFFF));
                return IntPtr.Zero;

            case WM_CLOSE:
                // 사용자가 경고 창을 닫을 수 없게 한다. 숨기기만 한다.
                HideCountdown();
                return IntPtr.Zero;

            case WM_DESTROY:
                RemoveTrayIcon();
                PostQuitMessage(0);
                return IntPtr.Zero;
        }

        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }

    private void OnTick()
    {
        var status = _poller.Latest;

        if (!_poller.ServiceReachable || status is null)
        {
            UpdateTrayTip("한일 TimeGuard — 서비스에 연결할 수 없습니다");
            HideCountdown();
            return;
        }

        UpdateTrayTip(BuildTrayTip(status));
        ShowNoticeIfNeeded(status);

        if (status.CountdownActive && status.CountdownSecondsLeft > 0)
            ShowCountdown(status);
        else
            HideCountdown();
    }

    private static string BuildTrayTip(StatusSnapshot status)
    {
        var tip = status.State switch
        {
            GuardState.Disabled => "한일 TimeGuard — 사용 제한 없음",
            GuardState.Allowed when status.RemainingSeconds is { } seconds =>
                $"한일 TimeGuard — {FormatRemaining(TimeSpan.FromSeconds(seconds))} 남음",
            GuardState.Allowed => "한일 TimeGuard — 사용 가능",
            GuardState.Blocked => "한일 TimeGuard — 허용 시간이 아닙니다",
            _ => "한일 TimeGuard"
        };

        // 툴팁은 127자까지만 표시된다.
        return tip.Length > 120 ? tip[..120] : tip;
    }

    private static string FormatRemaining(TimeSpan remaining)
    {
        if (remaining < TimeSpan.Zero) remaining = TimeSpan.Zero;

        if (remaining.TotalHours >= 1)
            return $"{(int)remaining.TotalHours}시간 {remaining.Minutes}분";
        if (remaining.TotalMinutes >= 1)
            return $"{(int)remaining.TotalMinutes}분";

        return $"{(int)remaining.TotalSeconds}초";
    }

    private void ShowNoticeIfNeeded(StatusSnapshot status)
    {
        if (status.NoticeMinutes is not { } minutes || status.NoticeId == 0) return;

        // 서비스가 경고마다 번호를 올려 주므로 같은 경고를 두 번 띄우지 않는다.
        // 같은 분 단위 경고가 다음 날 다시 와도 번호가 다르므로 정상적으로 표시된다.
        if (status.NoticeId == _lastNoticeId) return;
        _lastNoticeId = status.NoticeId;

        var action = DescribeAction(status.Action);
        ShowBalloon(
            title: $"{minutes}분 뒤 {action}",
            text: string.IsNullOrWhiteSpace(status.Message)
                ? $"허용된 사용 시간이 {minutes}분 남았습니다. 작업 중인 내용을 저장해 주세요."
                : status.Message,
            warning: true);
    }

    private void ShowCountdown(StatusSnapshot status)
    {
        var action = DescribeAction(status.Action);

        _titleText = status.State == GuardState.Blocked
            ? $"허용된 사용 시간이 아닙니다 — 곧 {action}됩니다"
            : $"허용된 사용 시간이 끝났습니다 — 곧 {action}됩니다";

        _countdownText = $"{status.CountdownSecondsLeft}초";

        _messageText = string.IsNullOrWhiteSpace(status.Message)
            ? "작업 중인 내용을 지금 저장해 주세요."
            : status.Message;

        _footerText = status.NextAllowedStart is { } next
            ? $"다음 사용 가능 시각: {next:M월 d일 HH:mm}  ·  문의: 관리자"
            : "문의: 관리자";

        if (!_countdownVisible)
        {
            ShowWindow(_hwnd, SW_SHOWNOACTIVATE);
            _countdownVisible = true;
        }

        // 전체 화면 프로그램 위에도 계속 보이도록 매번 최상위를 다시 지정한다.
        SetWindowPos(_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);

        InvalidateRect(_hwnd, IntPtr.Zero, false);
    }

    private void HideCountdown()
    {
        if (!_countdownVisible) return;

        ShowWindow(_hwnd, SW_HIDE);
        _countdownVisible = false;
    }

    private void OnPaint(IntPtr hWnd)
    {
        var hdc = BeginPaint(hWnd, out var paint);

        try
        {
            if (!GetClientRect(hWnd, out var client)) return;

            var background = CreateSolidBrush(Rgb(18, 18, 24));
            var accent = CreateSolidBrush(Rgb(203, 51, 68));

            try
            {
                FillRect(hdc, ref client, background);

                var accentBar = client with { Bottom = client.Top + Math.Max(4, client.Height / 40) };
                FillRect(hdc, ref accentBar, accent);

                SetBkMode(hdc, TRANSPARENT);

                var height = client.Height;
                var padding = client.Width / 20;

                DrawLine(hdc, _titleText,
                    Area(client, padding, (int)(height * 0.12), (int)(height * 0.20)),
                    fontSize: (int)(height * 0.095), bold: true, color: Rgb(255, 209, 214),
                    wrap: false);

                DrawLine(hdc, _countdownText,
                    Area(client, padding, (int)(height * 0.30), (int)(height * 0.32)),
                    fontSize: (int)(height * 0.30), bold: true, color: Rgb(255, 255, 255),
                    wrap: false);

                DrawLine(hdc, _messageText,
                    Area(client, padding, (int)(height * 0.64), (int)(height * 0.18)),
                    fontSize: (int)(height * 0.075), bold: false, color: Rgb(226, 226, 234),
                    wrap: true);

                DrawLine(hdc, _footerText,
                    Area(client, padding, (int)(height * 0.84), (int)(height * 0.10)),
                    fontSize: (int)(height * 0.058), bold: false, color: Rgb(150, 150, 165),
                    wrap: false);
            }
            finally
            {
                DeleteObject(background);
                DeleteObject(accent);
            }
        }
        finally
        {
            EndPaint(hWnd, ref paint);
        }
    }

    private static RECT Area(RECT client, int padding, int top, int height) => new()
    {
        Left = client.Left + padding,
        Right = client.Right - padding,
        Top = client.Top + top,
        Bottom = client.Top + top + height
    };

    private static void DrawLine(IntPtr hdc, string text, RECT area, int fontSize, bool bold, uint color, bool wrap)
    {
        if (string.IsNullOrEmpty(text)) return;

        var font = CreateFontW(
            height: -Math.Max(10, fontSize),
            width: 0, escapement: 0, orientation: 0,
            weight: bold ? FW_BOLD : FW_NORMAL,
            italic: 0, underline: 0, strikeOut: 0,
            charSet: HANGEUL_CHARSET,
            outputPrecision: 0, clipPrecision: 0,
            quality: CLEARTYPE_QUALITY,
            pitchAndFamily: 0,
            faceName: "맑은 고딕");

        var previousFont = SelectObject(hdc, font);

        try
        {
            SetTextColor(hdc, color);

            var format = DT_CENTER | DT_NOPREFIX |
                         (wrap ? DT_WORDBREAK : DT_SINGLELINE | DT_VCENTER);

            DrawTextW(hdc, text, text.Length, ref area, format);
        }
        finally
        {
            SelectObject(hdc, previousFont);
            DeleteObject(font);
        }
    }

    // ---- 트레이 아이콘 ----

    private void AddTrayIcon()
    {
        if (_trayIconAdded) return;

        var data = CreateTrayData(NIF_MESSAGE | NIF_ICON | NIF_TIP);
        data.szTip = string.IsNullOrEmpty(_lastTip) ? "한일 TimeGuard" : _lastTip;

        _trayIconAdded = Shell_NotifyIconW(NIM_ADD, ref data);
    }

    private void RemoveTrayIcon()
    {
        if (!_trayIconAdded) return;

        var data = CreateTrayData(0);
        Shell_NotifyIconW(NIM_DELETE, ref data);
        _trayIconAdded = false;
    }

    private void UpdateTrayTip(string tip)
    {
        if (tip == _lastTip) return;
        _lastTip = tip;

        if (!_trayIconAdded)
        {
            AddTrayIcon();
            return;
        }

        var data = CreateTrayData(NIF_TIP);
        data.szTip = tip;
        Shell_NotifyIconW(NIM_MODIFY, ref data);
    }

    private void ShowBalloon(string title, string text, bool warning)
    {
        if (!_trayIconAdded) AddTrayIcon();
        if (!_trayIconAdded) return;

        var data = CreateTrayData(NIF_INFO);
        data.szInfoTitle = Truncate(title, 60);
        data.szInfo = Truncate(text, 250);
        data.dwInfoFlags = warning ? NIIF_WARNING : NIIF_INFO;

        Shell_NotifyIconW(NIM_MODIFY, ref data);
    }

    private NOTIFYICONDATA CreateTrayData(uint flags) => new()
    {
        cbSize = (uint)Marshal.SizeOf<NOTIFYICONDATA>(),
        hWnd = _hwnd,
        uID = TrayIconId,
        uFlags = flags,
        uCallbackMessage = WM_TRAYICON,
        hIcon = LoadIconW(IntPtr.Zero, IDI_WARNING),
        szTip = string.Empty,
        szInfo = string.Empty,
        szInfoTitle = string.Empty
    };

    private static string Truncate(string text, int max) =>
        text.Length <= max ? text : text[..max];

    private void OnTrayMessage(uint mouseMessage)
    {
        switch (mouseMessage)
        {
            case WM_LBUTTONUP:
                ShowStatusDialog();
                break;

            case WM_RBUTTONUP:
                ShowContextMenu();
                break;
        }
    }

    private void ShowContextMenu()
    {
        var menu = CreatePopupMenu();
        if (menu == IntPtr.Zero) return;

        try
        {
            AppendMenuW(menu, MF_STRING, new UIntPtr(MenuShowStatus), "사용 시간 상태 보기(&S)");
            AppendMenuW(menu, MF_SEPARATOR, UIntPtr.Zero, null);
            AppendMenuW(menu, MF_STRING | MF_GRAYED, new UIntPtr(MenuShowRemaining), _lastTip);

            GetCursorPos(out var cursor);

            // 메뉴가 바로 닫히지 않도록 창을 앞으로 가져온다.
            SetForegroundWindow(_hwnd);
            TrackPopupMenu(menu, TPM_RIGHTBUTTON, cursor.X, cursor.Y, 0, _hwnd, IntPtr.Zero);
        }
        finally
        {
            DestroyMenu(menu);
        }
    }

    private void OnCommand(uint commandId)
    {
        if (commandId == MenuShowStatus) ShowStatusDialog();
    }

    private void ShowStatusDialog()
    {
        var status = _poller.Latest;

        if (!_poller.ServiceReachable || status is null)
        {
            MessageBoxW(IntPtr.Zero,
                "TimeGuard 서비스에 연결할 수 없습니다.\n관리자에게 문의해 주세요.",
                "한일 TimeGuard", MB_OK | MB_ICONINFORMATION | MB_TOPMOST);
            return;
        }

        var lines = new List<string>();

        switch (status.State)
        {
            case GuardState.Disabled:
                lines.Add("현재 사용 시간 제한이 적용되지 않습니다.");
                if (status.SuspendedUntil is { } suspended)
                    lines.Add($"일시 중지: {suspended:yyyy-MM-dd HH:mm} 까지");
                break;

            case GuardState.Allowed:
                if (status.RemainingSeconds is { } seconds)
                    lines.Add($"남은 사용 시간: {FormatRemaining(TimeSpan.FromSeconds(seconds))}");
                if (status.WindowEnd is { } end)
                    lines.Add($"사용 종료 시각: {end:yyyy-MM-dd HH:mm}");
                if (status.ExtensionApplied)
                    lines.Add("관리자 연장이 적용되어 있습니다.");
                break;

            case GuardState.Blocked:
                lines.Add("지금은 허용된 사용 시간이 아닙니다.");
                if (status.NextAllowedStart is { } next)
                    lines.Add($"다음 사용 가능 시각: {next:yyyy-MM-dd HH:mm}");
                break;
        }

        lines.Add(string.Empty);
        lines.Add($"시간 초과 시 조치: {DescribeAction(status.Action)}");

        MessageBoxW(IntPtr.Zero, string.Join('\n', lines),
            "한일 TimeGuard — 사용 시간 안내", MB_OK | MB_ICONINFORMATION | MB_TOPMOST);
    }

    internal static string DescribeAction(GuardAction action) => action switch
    {
        GuardAction.Shutdown => "전원이 차단",
        GuardAction.LogOff => "로그오프",
        GuardAction.Lock => "화면이 잠금",
        _ => "조치가 실행"
    };

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        if (_hwnd != IntPtr.Zero)
        {
            KillTimer(_hwnd, TimerId);
            RemoveTrayIcon();
            DestroyWindow(_hwnd);
            _hwnd = IntPtr.Zero;
        }
    }
}
