using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using static Hanil.TimeGuard.SetupKit.Ui.NativeUi;

namespace Hanil.TimeGuard.SetupKit.Ui;

/// <summary>설치 전에 물어볼 예/아니오 항목.</summary>
public sealed record SetupChoice(string Key, string Label, string Hint, bool DefaultOn);

/// <summary>설치 전에 물어볼 입력 항목.</summary>
public sealed record SetupTextField(string Key, string Label, string DefaultValue, string Hint, bool NumbersOnly = false);

/// <summary>사용자가 고른 값. 설치 동작에 넘어간다.</summary>
public sealed class SetupAnswers
{
    private readonly Dictionary<string, bool> _choices = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _texts = new(StringComparer.Ordinal);

    internal void SetChoice(string key, bool value) => _choices[key] = value;
    internal void SetText(string key, string value) => _texts[key] = value;

    public bool Choice(string key, bool fallback = false) =>
        _choices.TryGetValue(key, out var value) ? value : fallback;

    public string Text(string key, string fallback = "") =>
        _texts.TryGetValue(key, out var value) && value.Length > 0 ? value : fallback;

    public int Number(string key, int fallback) =>
        int.TryParse(Text(key), out var value) ? value : fallback;
}

/// <summary>설치 중 진행 상황을 화면에 알리는 통로.</summary>
public interface ISetupProgress
{
    /// <summary>한 단계를 마쳤다.</summary>
    void Done(string text);

    /// <summary>한 단계를 시작한다.</summary>
    void Step(string text);

    /// <summary>알아 두면 좋은 내용.</summary>
    void Note(string text);

    /// <summary>문제가 있었지만 설치는 계속한다.</summary>
    void Warn(string text);
}

/// <summary>설치나 제거가 끝난 결과.</summary>
public sealed record SetupOutcome(
    bool Success,
    string Heading,
    string Body,
    string? CopyText = null,
    string? CopyButtonText = null,
    string? OpenUrl = null,
    string? OpenButtonText = null);

/// <summary>
/// 설치 화면.
///
/// 첫 화면 → (물어볼 게 있으면) 선택 화면 → 진행 화면 → 끝 화면 순서로 넘어간다.
/// 실제 설치 작업은 별도 스레드에서 돌리고, 진행 상황만 창으로 보낸다.
/// 그래야 설치 중에도 창이 멈추지 않는다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class SetupWizard : IDisposable
{
    private const string ClassName = "HanilTimeGuardSetupWindow";

    private const int IdInstall = 1001;
    private const int IdRemove = 1002;
    private const int IdClose = 1003;
    private const int IdBack = 1004;
    private const int IdStart = 1005;
    private const int IdCopy = 1006;
    private const int IdOpen = 1007;
    private const int IdChoiceBase = 1100;
    private const int IdTextBase = 1200;

    private enum Page { Welcome, Options, Progress, Done }

    // ---- 겉모습 ----
    private const int BaseWidth = 620;
    private const int BaseHeight = 508;
    private const int Margin = 28;
    private const int HeaderHeight = 88;
    private const int FooterHeight = 62;

    private static readonly uint ColorText = Rgb(28, 28, 30);
    private static readonly uint ColorMuted = Rgb(104, 104, 112);
    private static readonly uint ColorAccent = Rgb(0, 90, 158);
    private static readonly uint ColorGood = Rgb(20, 118, 70);
    private static readonly uint ColorBad = Rgb(178, 40, 40);
    private static readonly uint ColorWhite = Rgb(255, 255, 255);
    private static readonly uint ColorFooter = Rgb(240, 240, 243);
    private static readonly uint ColorLine = Rgb(222, 222, 228);

    private static readonly Dictionary<IntPtr, SetupWizard> Instances = new();
    private static bool _classRegistered;
    private static WndProc? _registeredProc;   // GC 가 수거하지 못하게 붙잡아 둔다

    private readonly ConcurrentQueue<(string Text, uint Color)> _pending = new();
    private readonly Dictionary<IntPtr, uint> _textColors = new();
    private readonly List<IntPtr> _welcomeControls = new();
    private readonly List<IntPtr> _optionControls = new();
    private readonly List<IntPtr> _progressControls = new();
    private readonly List<IntPtr> _doneControls = new();
    private readonly Dictionary<string, IntPtr> _choiceBoxes = new(StringComparer.Ordinal);
    private readonly Dictionary<string, IntPtr> _textBoxes = new(StringComparer.Ordinal);

    private readonly string _caption;
    private readonly string _heading;

    private IntPtr _hwnd;
    private IntPtr _instance;
    private IntPtr _fontHeading, _fontSub, _fontBody, _fontBold, _fontLog, _fontButton;
    private IntPtr _brushWhite, _brushFooter;

    private IntPtr _statusLabel, _welcomeBody;
    private IntPtr _progressBar, _logBox, _progressTitle;
    private IntPtr _doneHeading, _doneBody;
    private IntPtr _installButton, _removeButton, _closeButton, _backButton, _startButton, _copyButton, _openButton;

    private Page _page = Page.Welcome;
    private bool _finished;
    private bool _working;
    private bool _removing;
    private int _dpi = 96;
    private int _exitCode;

    private SetupOutcome? _outcome;

    public SetupWizard(string caption, string heading)
    {
        _caption = caption;
        _heading = heading;
    }

    // ---- 바깥에서 채우는 값들 ----

    public string Subheading { get; set; } = string.Empty;
    public string WelcomeBody { get; set; } = string.Empty;
    public string StatusLine { get; set; } = string.Empty;

    /// <summary>상태 줄 색. true 면 초록(이미 설치됨), false 면 회색.</summary>
    public bool StatusIsGood { get; set; }

    public string InstallButtonText { get; set; } = "설치";
    public string RemoveConfirmText { get; set; } = "정말 제거할까요?";
    public bool CanRemove { get; set; }

    public string OptionsHeading { get; set; } = "설치 전에 두 가지만 확인합니다";
    public List<SetupChoice> Choices { get; } = new();
    public List<SetupTextField> TextFields { get; } = new();

    public Func<ISetupProgress, SetupAnswers, SetupOutcome>? InstallAction { get; set; }
    public Func<ISetupProgress, SetupOutcome>? RemoveAction { get; set; }

    /// <summary>창을 띄우고 닫힐 때까지 기다린다. 프로그램 종료 코드를 돌려준다.</summary>
    public int Run()
    {
        EnableVisualStyles();

        _instance = GetModuleHandleW(null);
        _dpi = ReadSystemDpi();

        EnsureClassRegistered();
        CreateFonts();

        var rect = new RECT { Left = 0, Top = 0, Right = S(BaseWidth), Bottom = S(BaseHeight) };
        const uint style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
        AdjustWindowRect(ref rect, style, false);

        var width = rect.Width;
        var height = rect.Height;
        var x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
        var y = (GetSystemMetrics(SM_CYSCREEN) - height) / 3;   // 살짝 위쪽이 보기 좋다

        _hwnd = CreateWindowExW(
            WS_EX_CONTROLPARENT, ClassName, _caption, style,
            x, y, width, height,
            IntPtr.Zero, IntPtr.Zero, _instance, IntPtr.Zero);

        if (_hwnd == IntPtr.Zero) return 1;

        Instances[_hwnd] = this;

        BuildControls();
        SwitchTo(Page.Welcome);

        ShowWindow(_hwnd, SW_SHOWNORMAL);
        SetForegroundWindow(_hwnd);

        while (!_finished && GetMessageW(out var message, IntPtr.Zero, 0, 0) > 0)
        {
            if (IsWindow(_hwnd) && IsDialogMessageW(_hwnd, ref message)) continue;

            TranslateMessage(ref message);
            DispatchMessageW(ref message);
        }

        return _exitCode;
    }

    // ---- 크기 계산 ----

    /// <summary>화면 배율에 맞게 좌표를 키운다.</summary>
    private int S(int value) => value * _dpi / 96;

    private static int ReadSystemDpi()
    {
        try { return (int)GetDpiForSystem(); }
        catch (Exception) { return 96; }
    }

    [DllImport("user32.dll")]
    private static extern uint GetDpiForSystem();

    private static void EnableVisualStyles()
    {
        try
        {
            var controls = new INITCOMMONCONTROLSEX
            {
                dwSize = (uint)Marshal.SizeOf<INITCOMMONCONTROLSEX>(),
                dwICC = ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES
            };

            InitCommonControlsEx(ref controls);
        }
        catch (Exception)
        {
            // 공용 컨트롤 등록에 실패해도 기본 모양으로는 나온다.
        }
    }

    private void EnsureClassRegistered()
    {
        if (_classRegistered) return;

        _registeredProc = StaticWindowProcedure;
        _brushWhite = CreateSolidBrush(ColorWhite);

        var windowClass = new WNDCLASSEX
        {
            cbSize = (uint)Marshal.SizeOf<WNDCLASSEX>(),
            lpfnWndProc = Marshal.GetFunctionPointerForDelegate(_registeredProc),
            hInstance = _instance,
            hIcon = LoadIconW(IntPtr.Zero, IDI_APPLICATION),
            hCursor = LoadCursorW(IntPtr.Zero, IDC_ARROW),
            hbrBackground = _brushWhite,
            lpszClassName = ClassName
        };

        var atom = RegisterClassExW(ref windowClass);

        // 1410 = 이미 등록됨
        if (atom != 0 || Marshal.GetLastWin32Error() == 1410) _classRegistered = true;
    }

    private static IntPtr StaticWindowProcedure(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam) =>
        Instances.TryGetValue(hWnd, out var wizard)
            ? wizard.WindowProcedure(hWnd, msg, wParam, lParam)
            : DefWindowProcW(hWnd, msg, wParam, lParam);

    private void CreateFonts()
    {
        IntPtr Font(int size, int weight) => CreateFontW(
            -S(size), 0, 0, 0, weight, 0, 0, 0, HANGEUL_CHARSET,
            0, 0, CLEARTYPE_QUALITY, 0, "맑은 고딕");

        _fontHeading = Font(21, FW_SEMIBOLD);
        _fontSub = Font(14, FW_NORMAL);
        _fontBody = Font(15, FW_NORMAL);
        _fontBold = Font(16, FW_SEMIBOLD);
        _fontLog = Font(14, FW_NORMAL);
        _fontButton = Font(15, FW_NORMAL);

        _brushFooter = CreateSolidBrush(ColorFooter);
        if (_brushWhite == IntPtr.Zero) _brushWhite = CreateSolidBrush(ColorWhite);
    }

    // ---- 화면 만들기 ----

    private void BuildControls()
    {
        var contentWidth = BaseWidth - Margin * 2;

        // --- 머리말 (모든 화면 공통) ---
        var heading = Label(_heading, Margin, 22, contentWidth, 30, _fontHeading, ColorText);
        _textColors[heading] = ColorText;

        if (Subheading.Length > 0)
            Label(Subheading, Margin, 54, contentWidth, 22, _fontSub, ColorMuted);

        // --- 첫 화면 ---
        _statusLabel = Label(StatusLine, Margin, HeaderHeight + 18, contentWidth, 24, _fontBold,
            StatusIsGood ? ColorGood : ColorMuted);
        _welcomeControls.Add(_statusLabel);

        _welcomeBody = Label(WelcomeBody, Margin, HeaderHeight + 52, contentWidth,
            BaseHeight - FooterHeight - HeaderHeight - 70, _fontBody, ColorText);
        _welcomeControls.Add(_welcomeBody);

        // --- 선택 화면 ---
        if (HasOptions)
        {
            _optionControls.Add(Label(OptionsHeading, Margin, HeaderHeight + 18, contentWidth, 24, _fontBold, ColorText));

            var y = HeaderHeight + 56;

            for (var i = 0; i < Choices.Count; i++)
            {
                var choice = Choices[i];

                var box = CreateWindowExW(0, "BUTTON", choice.Label,
                    WS_CHILD | WS_TABSTOP | BS_AUTOCHECKBOX,
                    S(Margin), S(y), S(contentWidth), S(24),
                    _hwnd, new IntPtr(IdChoiceBase + i), _instance, IntPtr.Zero);

                SendMessageW(box, WM_SETFONT, _fontBody, IntPtr.Zero);
                SendMessageW(box, BM_SETCHECK, new IntPtr(choice.DefaultOn ? 1 : 0), IntPtr.Zero);

                _choiceBoxes[choice.Key] = box;
                _optionControls.Add(box);
                _textColors[box] = ColorText;

                y += 26;

                if (choice.Hint.Length > 0)
                {
                    _optionControls.Add(Label(choice.Hint, Margin + 22, y, contentWidth - 22, 38, _fontSub, ColorMuted));
                    y += 42;
                }
                else
                {
                    y += 8;
                }
            }

            for (var i = 0; i < TextFields.Count; i++)
            {
                var field = TextFields[i];

                _optionControls.Add(Label(field.Label, Margin, y, contentWidth, 22, _fontBody, ColorText));
                y += 26;

                var style = WS_CHILD | WS_TABSTOP;
                if (field.NumbersOnly) style |= ES_NUMBER;

                var edit = CreateWindowExW(WS_EX_CLIENTEDGE, "EDIT", field.DefaultValue,
                    style,
                    S(Margin), S(y), S(150), S(28),
                    _hwnd, new IntPtr(IdTextBase + i), _instance, IntPtr.Zero);

                SendMessageW(edit, WM_SETFONT, _fontBody, IntPtr.Zero);

                _textBoxes[field.Key] = edit;
                _optionControls.Add(edit);

                if (field.Hint.Length > 0)
                    _optionControls.Add(Label(field.Hint, Margin + 162, y + 5, contentWidth - 162, 22, _fontSub, ColorMuted));

                y += 40;
            }
        }

        // --- 진행 화면 ---
        _progressTitle = Label("설치하고 있습니다. 잠시만 기다려 주세요.",
            Margin, HeaderHeight + 18, contentWidth, 24, _fontBold, ColorText);
        _progressControls.Add(_progressTitle);

        _progressBar = CreateWindowExW(0, ProgressClass, null,
            WS_CHILD | PBS_MARQUEE,
            S(Margin), S(HeaderHeight + 52), S(contentWidth), S(10),
            _hwnd, IntPtr.Zero, _instance, IntPtr.Zero);

        _progressControls.Add(_progressBar);

        _logBox = CreateWindowExW(0, "EDIT", null,
            WS_CHILD | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
            S(Margin), S(HeaderHeight + 76), S(contentWidth),
            S(BaseHeight - FooterHeight - HeaderHeight - 94),
            _hwnd, IntPtr.Zero, _instance, IntPtr.Zero);

        SendMessageW(_logBox, WM_SETFONT, _fontLog, IntPtr.Zero);
        _progressControls.Add(_logBox);

        // --- 끝 화면 ---
        _doneHeading = Label(string.Empty, Margin, HeaderHeight + 18, contentWidth, 28, _fontBold, ColorGood);
        _doneControls.Add(_doneHeading);

        // 안내가 길어질 수 있어 스크롤되는 읽기 전용 칸으로 만든다.
        // 테두리를 주지 않아 겉보기에는 그냥 글이다.
        _doneBody = CreateWindowExW(0, "EDIT", null,
            WS_CHILD | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
            S(Margin), S(HeaderHeight + 54), S(contentWidth),
            S(BaseHeight - FooterHeight - HeaderHeight - 110),
            _hwnd, IntPtr.Zero, _instance, IntPtr.Zero);

        SendMessageW(_doneBody, WM_SETFONT, _fontBody, IntPtr.Zero);
        _doneControls.Add(_doneBody);

        _copyButton = Button("복사", IdCopy, Margin, BaseHeight - FooterHeight - 46, 150, 32);
        _doneControls.Add(_copyButton);

        _openButton = Button("열기", IdOpen, Margin + 158, BaseHeight - FooterHeight - 46, 170, 32);
        _doneControls.Add(_openButton);

        // --- 아래쪽 단추 (화면마다 보이는 게 다르다) ---
        var buttonY = BaseHeight - FooterHeight + 14;
        var right = BaseWidth - Margin;

        _closeButton = Button("닫기", IdClose, right - 104, buttonY, 104, 34);
        _installButton = Button(InstallButtonText, IdInstall, right - 216, buttonY, 104, 34, isDefault: true);
        _removeButton = Button("제거", IdRemove, Margin, buttonY, 104, 34);
        _backButton = Button("뒤로", IdBack, Margin, buttonY, 104, 34);
        _startButton = Button("설치 시작", IdStart, right - 216, buttonY, 104, 34, isDefault: true);
    }

    private bool HasOptions => Choices.Count > 0 || TextFields.Count > 0;

    private IntPtr Label(string text, int x, int y, int width, int height, IntPtr font, uint color)
    {
        var handle = CreateWindowExW(0, "STATIC", text,
            WS_CHILD | SS_LEFT | SS_NOPREFIX,
            S(x), S(y), S(width), S(height),
            _hwnd, IntPtr.Zero, _instance, IntPtr.Zero);

        SendMessageW(handle, WM_SETFONT, font, IntPtr.Zero);
        _textColors[handle] = color;

        return handle;
    }

    private IntPtr Button(string text, int id, int x, int y, int width, int height, bool isDefault = false)
    {
        var handle = CreateWindowExW(0, "BUTTON", text,
            WS_CHILD | WS_TABSTOP | (isDefault ? BS_DEFPUSHBUTTON : BS_PUSHBUTTON),
            S(x), S(y), S(width), S(height),
            _hwnd, new IntPtr(id), _instance, IntPtr.Zero);

        SendMessageW(handle, WM_SETFONT, _fontButton, IntPtr.Zero);
        return handle;
    }

    // ---- 화면 전환 ----

    private void SwitchTo(Page page)
    {
        _page = page;

        Show(_welcomeControls, page == Page.Welcome);
        Show(_optionControls, page == Page.Options);
        Show(_progressControls, page == Page.Progress);
        Show(_doneControls, page == Page.Done);

        ShowWindow(_installButton, page == Page.Welcome ? SW_SHOW : SW_HIDE);
        ShowWindow(_removeButton, page == Page.Welcome && CanRemove ? SW_SHOW : SW_HIDE);
        ShowWindow(_backButton, page == Page.Options ? SW_SHOW : SW_HIDE);
        ShowWindow(_startButton, page == Page.Options ? SW_SHOW : SW_HIDE);
        ShowWindow(_closeButton, page != Page.Progress ? SW_SHOW : SW_HIDE);

        if (page == Page.Done)
        {
            var hasCopy = !string.IsNullOrEmpty(_outcome?.CopyText);
            var hasOpen = !string.IsNullOrEmpty(_outcome?.OpenUrl);

            ShowWindow(_copyButton, hasCopy ? SW_SHOW : SW_HIDE);
            ShowWindow(_openButton, hasOpen ? SW_SHOW : SW_HIDE);
        }
        else
        {
            ShowWindow(_copyButton, SW_HIDE);
            ShowWindow(_openButton, SW_HIDE);
        }

        if (page == Page.Welcome) SetFocus(_installButton);
        if (page == Page.Options) SetFocus(_startButton);
        if (page == Page.Done) SetFocus(_closeButton);
    }

    private static void Show(List<IntPtr> controls, bool visible)
    {
        foreach (var control in controls)
            ShowWindow(control, visible ? SW_SHOW : SW_HIDE);
    }

    // ---- 메시지 처리 ----

    private IntPtr WindowProcedure(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        switch (msg)
        {
            case WM_PAINT:
                PaintBackground(hWnd);
                return IntPtr.Zero;

            case WM_CTLCOLORSTATIC:
            case WM_CTLCOLORBTN:
            {
                // 글자 색을 정하고 배경은 창과 같은 흰색으로 맞춘다.
                var color = _textColors.TryGetValue(lParam, out var wanted) ? wanted : ColorText;

                SetTextColor(wParam, color);
                SetBkColor(wParam, ColorWhite);

                return _brushWhite;
            }

            case WM_COMMAND:
                HandleCommand((int)(wParam.ToInt64() & 0xFFFF));
                return IntPtr.Zero;

            case WM_SETUP_PROGRESS:
                DrainProgress();
                return IntPtr.Zero;

            case WM_SETUP_FINISHED:
                ShowResult();
                return IntPtr.Zero;

            case WM_CLOSE:
                // 설치 중에는 닫지 못하게 한다. 중간에 멈추면 더 곤란해진다.
                if (_working)
                {
                    MessageBoxW(_hwnd,
                        "설치하고 있습니다. 끝날 때까지 기다려 주세요.",
                        _caption, MB_OK | MB_ICONINFORMATION);

                    return IntPtr.Zero;
                }

                DestroyWindow(_hwnd);
                return IntPtr.Zero;

            case WM_DESTROY:
                Instances.Remove(hWnd);
                _finished = true;
                PostQuitMessage(0);
                return IntPtr.Zero;
        }

        return DefWindowProcW(hWnd, msg, wParam, lParam);
    }

    private void PaintBackground(IntPtr hWnd)
    {
        var hdc = BeginPaint(hWnd, out var paint);

        try
        {
            GetClientRect(hWnd, out var client);

            var body = client;
            FillRect(hdc, ref body, _brushWhite);

            // 아래쪽 단추 자리는 연한 회색으로 구분한다.
            var footer = new RECT
            {
                Left = client.Left,
                Top = client.Bottom - S(FooterHeight),
                Right = client.Right,
                Bottom = client.Bottom
            };

            FillRect(hdc, ref footer, _brushFooter);

            var line = new RECT
            {
                Left = client.Left,
                Top = footer.Top,
                Right = client.Right,
                Bottom = footer.Top + 1
            };

            var lineBrush = CreateSolidBrush(ColorLine);
            FillRect(hdc, ref line, lineBrush);
            DeleteObject(lineBrush);

            // 머리말 아래에도 같은 선을 긋는다.
            var headerLine = new RECT
            {
                Left = client.Left,
                Top = S(HeaderHeight) - 1,
                Right = client.Right,
                Bottom = S(HeaderHeight)
            };

            var headerBrush = CreateSolidBrush(ColorLine);
            FillRect(hdc, ref headerLine, headerBrush);
            DeleteObject(headerBrush);
        }
        finally
        {
            EndPaint(hWnd, ref paint);
        }
    }

    private void HandleCommand(int controlId)
    {
        switch (controlId)
        {
            case IdInstall:
                if (HasOptions) SwitchTo(Page.Options);
                else StartWork(removing: false);
                break;

            case IdStart:
                StartWork(removing: false);
                break;

            case IdBack:
                SwitchTo(Page.Welcome);
                break;

            case IdRemove:
                if (ConfirmRemove()) StartWork(removing: true);
                break;

            case IdCopy:
                if (_outcome?.CopyText is { Length: > 0 } text && CopyToClipboard(_hwnd, text))
                    SetWindowTextW(_copyButton, "복사했습니다");
                break;

            case IdOpen:
                if (_outcome?.OpenUrl is { Length: > 0 } url)
                    ShellExecuteW(_hwnd, "open", url, null, null, SW_SHOWNORMAL);
                break;

            case IdClose:
            case IDCANCEL:
                if (!_working) DestroyWindow(_hwnd);
                break;
        }
    }

    private bool ConfirmRemove() =>
        MessageBoxW(_hwnd, RemoveConfirmText, _caption,
            MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2) == IDYES;

    // ---- 설치 작업 ----

    private void StartWork(bool removing)
    {
        if (_working) return;

        _working = true;
        _removing = removing;
        _outcome = null;

        var answers = ReadAnswers();

        SetWindowTextW(_progressTitle, removing
            ? "제거하고 있습니다. 잠시만 기다려 주세요."
            : "설치하고 있습니다. 잠시만 기다려 주세요.");

        SetWindowTextW(_logBox, string.Empty);
        SwitchTo(Page.Progress);

        // 막대를 계속 흐르게 둔다. 단계마다 걸리는 시간이 제각각이라
        // 몇 퍼센트라고 표시하면 오히려 잘못된 느낌을 준다.
        SendMessageW(_progressBar, PBM_SETMARQUEE, new IntPtr(1), new IntPtr(30));

        var progress = new Reporter(this);
        var hwnd = _hwnd;

        Task.Run(() =>
        {
            SetupOutcome outcome;

            try
            {
                outcome = removing
                    ? RemoveAction?.Invoke(progress) ?? new SetupOutcome(false, "제거할 수 없습니다", "제거 기능이 준비되지 않았습니다.")
                    : InstallAction?.Invoke(progress, answers) ?? new SetupOutcome(false, "설치할 수 없습니다", "설치 기능이 준비되지 않았습니다.");
            }
            catch (Exception ex)
            {
                progress.Warn(ex.Message);

                outcome = new SetupOutcome(false,
                    removing ? "제거하지 못했습니다" : "설치하지 못했습니다",
                    "예상하지 못한 문제가 생겼습니다.\r\n\r\n" + ex.Message);
            }

            _outcome = outcome;
            PostMessageW(hwnd, WM_SETUP_FINISHED, IntPtr.Zero, IntPtr.Zero);
        });
    }

    private SetupAnswers ReadAnswers()
    {
        var answers = new SetupAnswers();

        foreach (var (key, box) in _choiceBoxes)
            answers.SetChoice(key, SendMessageW(box, BM_GETCHECK, IntPtr.Zero, IntPtr.Zero).ToInt64() == 1);

        foreach (var (key, box) in _textBoxes)
            answers.SetText(key, ReadText(box).Trim());

        return answers;
    }

    private static string ReadText(IntPtr control)
    {
        var length = GetWindowTextLengthW(control);
        if (length <= 0) return string.Empty;

        var buffer = new StringBuilder(length + 1);
        GetWindowTextW(control, buffer, buffer.Capacity);

        return buffer.ToString();
    }

    /// <summary>작업 스레드가 쌓아 둔 줄을 화면에 옮긴다.</summary>
    private void DrainProgress()
    {
        while (_pending.TryDequeue(out var entry))
            AppendLine(entry.Text);
    }

    private void AppendLine(string text)
    {
        SendMessageW(_logBox, EM_SETSEL, new IntPtr(-1), new IntPtr(-1));
        SendMessageW(_logBox, EM_REPLACESEL, IntPtr.Zero, text + "\r\n");
        SendMessageW(_logBox, EM_SCROLLCARET, IntPtr.Zero, IntPtr.Zero);
    }

    private void ShowResult()
    {
        DrainProgress();

        _working = false;
        SendMessageW(_progressBar, PBM_SETMARQUEE, IntPtr.Zero, IntPtr.Zero);

        var outcome = _outcome ?? new SetupOutcome(false, "끝내지 못했습니다", "결과를 확인하지 못했습니다.");

        _exitCode = outcome.Success ? 0 : 1;

        _textColors[_doneHeading] = outcome.Success ? ColorGood : ColorBad;

        SetWindowTextW(_doneHeading, outcome.Heading);
        SetWindowTextW(_doneBody, outcome.Body);

        if (!string.IsNullOrEmpty(outcome.CopyButtonText))
            SetWindowTextW(_copyButton, outcome.CopyButtonText);

        if (!string.IsNullOrEmpty(outcome.OpenButtonText))
            SetWindowTextW(_openButton, outcome.OpenButtonText);

        // 제거를 마쳤으면 다시 설치할 수 있게 첫 화면 단추를 되돌려 둔다.
        if (_removing) CanRemove = false;

        SwitchTo(Page.Done);
    }

    /// <summary>작업 스레드에서 호출된다. 창을 직접 건드리지 않고 줄만 쌓아 둔다.</summary>
    private sealed class Reporter : ISetupProgress
    {
        private readonly SetupWizard _wizard;

        internal Reporter(SetupWizard wizard) => _wizard = wizard;

        public void Step(string text) => Push("   " + text);
        public void Done(string text) => Push("✓  " + text);
        public void Note(string text) => Push("    " + text);
        public void Warn(string text) => Push("!  " + text);

        private void Push(string text)
        {
            _wizard._pending.Enqueue((text, ColorText));
            PostMessageW(_wizard._hwnd, WM_SETUP_PROGRESS, IntPtr.Zero, IntPtr.Zero);
        }
    }

    public void Dispose()
    {
        foreach (var font in new[] { _fontHeading, _fontSub, _fontBody, _fontBold, _fontLog, _fontButton })
            if (font != IntPtr.Zero) DeleteObject(font);

        if (_brushFooter != IntPtr.Zero) DeleteObject(_brushFooter);

        if (_hwnd != IntPtr.Zero)
        {
            Instances.Remove(_hwnd);
            _hwnd = IntPtr.Zero;
        }
    }
}
