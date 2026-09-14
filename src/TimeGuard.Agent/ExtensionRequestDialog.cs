using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using Hanil.TimeGuard.Agent.Interop;
using static Hanil.TimeGuard.Agent.Interop.Win32;

namespace Hanil.TimeGuard.Agent;

/// <summary>사용자가 입력한 연장 요청 내용.</summary>
public sealed record ExtensionRequestInputResult(int Minutes, string Reason);

/// <summary>
/// 사용 시간 연장을 요청하는 작은 창.
/// WinForms 없이 표준 Win32 컨트롤로 만들었다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class ExtensionRequestDialog : IDisposable
{
    private const string ClassName = "HanilTimeGuardRequestDialog";

    private const int IdMinutes = 1001;
    private const int IdReason = 1002;
    private const int IdSubmit = 1003;
    private const int IdCancel = 1004;

    /// <summary>고를 수 있는 연장 시간. 화면 표시와 실제 분 수를 함께 둔다.</summary>
    private static readonly (string Label, int Minutes)[] Choices =
    {
        ("30분", 30),
        ("1시간", 60),
        ("2시간", 120),
        ("3시간", 180),
        ("4시간", 240)
    };

    private static bool _classRegistered;
    private static WndProc? _registeredProc; // GC 가 수거하지 못하게 붙잡아 둔다

    private readonly WndProc _wndProc;

    private IntPtr _hwnd;
    private IntPtr _minutesBox;
    private IntPtr _reasonBox;
    private IntPtr _font;
    private IntPtr _titleFont;

    private bool _submitted;
    private bool _finished;
    private ExtensionRequestInputResult? _result;

    public ExtensionRequestDialog() => _wndProc = WindowProcedure;

    /// <summary>창을 띄우고 사용자가 닫을 때까지 기다린다. 취소하면 null.</summary>
    public ExtensionRequestInputResult? Show()
    {
        var instance = GetModuleHandleW(null);
        EnsureClassRegistered(instance);

        const int width = 440;
        const int height = 330;

        var x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
        var y = (GetSystemMetrics(SM_CYSCREEN) - height) / 2;

        _hwnd = CreateWindowExW(
            WS_EX_TOPMOST,
            ClassName,
            "사용 시간 연장 요청",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
            x, y, width, height,
            IntPtr.Zero, IntPtr.Zero, instance, IntPtr.Zero);

        if (_hwnd == IntPtr.Zero) return null;

        // 창 핸들에서 이 인스턴스를 찾을 수 있도록 등록해 둔다.
        Instances[_hwnd] = this;

        BuildControls(instance);

        ShowWindow(_hwnd, (int)SW_SHOW);
        SetForegroundWindow(_hwnd);
        SetFocus(_reasonBox);

        // 창이 닫힐 때까지 여기서 메시지를 돌린다.
        while (!_finished && GetMessageW(out var message, IntPtr.Zero, 0, 0) > 0)
        {
            // Tab 이동과 Enter/Esc 가 동작하게 한다.
            if (IsWindow(_hwnd) && IsDialogMessageW(_hwnd, ref message)) continue;

            TranslateMessage(ref message);
            DispatchMessageW(ref message);
        }

        return _result;
    }

    private static readonly Dictionary<IntPtr, ExtensionRequestDialog> Instances = new();

    private static void EnsureClassRegistered(IntPtr instance)
    {
        if (_classRegistered) return;

        _registeredProc = StaticWindowProcedure;

        var windowClass = new WNDCLASSEX
        {
            cbSize = (uint)Marshal.SizeOf<WNDCLASSEX>(),
            lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_registeredProc),
            hInstance = instance,
            hIcon = LoadIconW(IntPtr.Zero, IDI_INFORMATION),
            hCursor = LoadCursorW(IntPtr.Zero, IDC_ARROW),
            hbrBackground = new IntPtr(16), // COLOR_BTNFACE + 1: 표준 대화 상자 배경
            lpszClassName = ClassName
        };

        var atom = RegisterClassExW(ref windowClass);

        // 1410 = 이미 등록됨. 다시 띄우는 경우이므로 그대로 진행한다.
        if (atom != 0 || Marshal.GetLastWin32Error() == 1410) _classRegistered = true;
    }

    private static IntPtr StaticWindowProcedure(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam) =>
        Instances.TryGetValue(hWnd, out var dialog)
            ? dialog.WindowProcedure(hWnd, msg, wParam, lParam)
            : DefWindowProcW(hWnd, msg, wParam, lParam);

    private void BuildControls(IntPtr instance)
    {
        _font = CreateFontW(-15, 0, 0, 0, FW_NORMAL, 0, 0, 0, HANGEUL_CHARSET,
            0, 0, CLEARTYPE_QUALITY, 0, "맑은 고딕");

        _titleFont = CreateFontW(-18, 0, 0, 0, FW_BOLD, 0, 0, 0, HANGEUL_CHARSET,
            0, 0, CLEARTYPE_QUALITY, 0, "맑은 고딕");

        var title = Label("사용 시간 연장을 요청합니다", 20, 18, 390, 26, instance);
        SendMessageW(title, WM_SETFONT, _titleFont, IntPtr.Zero);

        Label("관리자가 승인하면 그만큼 더 사용할 수 있습니다.", 20, 46, 390, 22, instance);

        Label("얼마나 더 필요하신가요?", 20, 82, 200, 22, instance);

        _minutesBox = CreateWindowExW(0, "COMBOBOX", null,
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | CBS_DROPDOWNLIST | WS_VSCROLL,
            20, 106, 160, 200, _hwnd, new IntPtr(IdMinutes), instance, IntPtr.Zero);

        SendMessageW(_minutesBox, WM_SETFONT, _font, IntPtr.Zero);

        foreach (var (label, _) in Choices)
            SendMessageW(_minutesBox, CB_ADDSTRING, IntPtr.Zero, label);

        SendMessageW(_minutesBox, CB_SETCURSEL, new IntPtr(1), IntPtr.Zero); // 기본 1시간

        Label("사유를 적어 주세요 (예: 납기 때문에 야근, 마감 작업 중)", 20, 146, 390, 22, instance);

        _reasonBox = CreateWindowExW(0x00000200, "EDIT", null,   // WS_EX_CLIENTEDGE
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_MULTILINE | ES_AUTOVSCROLL | ES_WANTRETURN | WS_VSCROLL,
            20, 170, 390, 70, _hwnd, new IntPtr(IdReason), instance, IntPtr.Zero);

        SendMessageW(_reasonBox, WM_SETFONT, _font, IntPtr.Zero);

        var submit = CreateWindowExW(0, "BUTTON", "요청 보내기",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
            230, 252, 110, 32, _hwnd, new IntPtr(IdSubmit), instance, IntPtr.Zero);

        SendMessageW(submit, WM_SETFONT, _font, IntPtr.Zero);

        var cancel = CreateWindowExW(0, "BUTTON", "취소",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            348, 252, 62, 32, _hwnd, new IntPtr(IdCancel), instance, IntPtr.Zero);

        SendMessageW(cancel, WM_SETFONT, _font, IntPtr.Zero);
    }

    private IntPtr Label(string text, int x, int y, int width, int height, IntPtr instance)
    {
        var handle = CreateWindowExW(0, "STATIC", text,
            WS_CHILD | WS_VISIBLE,
            x, y, width, height, _hwnd, IntPtr.Zero, instance, IntPtr.Zero);

        if (_font != IntPtr.Zero) SendMessageW(handle, WM_SETFONT, _font, IntPtr.Zero);
        return handle;
    }

    private IntPtr WindowProcedure(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        switch (msg)
        {
            case WM_COMMAND:
                var controlId = (int)(wParam.ToInt64() & 0xFFFF);

                if (controlId == IdSubmit)
                {
                    Submit();
                    return IntPtr.Zero;
                }

                if (controlId == IdCancel || controlId == 2) // 2 = IDCANCEL (Esc)
                {
                    Close();
                    return IntPtr.Zero;
                }

                break;

            case WM_CLOSE:
                Close();
                return IntPtr.Zero;

            case WM_DESTROY:
                Instances.Remove(hWnd);
                _finished = true;
                return IntPtr.Zero;
        }

        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }

    private void Submit()
    {
        var index = (int)SendMessageW(_minutesBox, CB_GETCURSEL, IntPtr.Zero, IntPtr.Zero).ToInt64();
        if (index < 0 || index >= Choices.Length) index = 1;

        var reason = ReadText(_reasonBox).Trim();

        if (reason.Length == 0)
        {
            MessageBoxW(_hwnd,
                "사유를 적어 주세요.\n\n관리자가 이 내용을 보고 승인 여부를 정합니다.\n" +
                "예) 납기 때문에 야근이 필요합니다\n" +
                "예) 월말 마감 작업이 남았습니다",
                "사용 시간 연장 요청", MB_OK | MB_ICONINFORMATION);

            SetFocus(_reasonBox);
            return;
        }

        // 너무 짧으면 관리자가 판단할 수 없다.
        if (reason.Length < 4)
        {
            MessageBoxW(_hwnd,
                "사유를 조금 더 자세히 적어 주세요.\n관리자가 보고 승인 여부를 정합니다.",
                "사용 시간 연장 요청", MB_OK | MB_ICONINFORMATION);

            SetFocus(_reasonBox);
            return;
        }

        _submitted = true;
        _result = new ExtensionRequestInputResult(Choices[index].Minutes, reason);
        Close();
    }

    private void Close()
    {
        if (!_submitted) _result = null;
        if (_hwnd != IntPtr.Zero) DestroyWindow(_hwnd);
    }

    private static string ReadText(IntPtr control)
    {
        var length = GetWindowTextLengthW(control);
        if (length <= 0) return string.Empty;

        var buffer = new StringBuilder(length + 1);
        GetWindowTextW(control, buffer, buffer.Capacity);

        return buffer.ToString();
    }

    public void Dispose()
    {
        if (_font != IntPtr.Zero) { DeleteObject(_font); _font = IntPtr.Zero; }
        if (_titleFont != IntPtr.Zero) { DeleteObject(_titleFont); _titleFont = IntPtr.Zero; }

        if (_hwnd != IntPtr.Zero)
        {
            Instances.Remove(_hwnd);
            _hwnd = IntPtr.Zero;
        }
    }
}
