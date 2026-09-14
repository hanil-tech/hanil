using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.SetupKit;
using Hanil.TimeGuard.SetupKit.Ui;
using Microsoft.Win32;

[assembly: SupportedOSPlatform("windows")]

// 직원 PC 용 설치 프로그램.
// 더블클릭하면 Windows 가 관리자 권한을 물어보고, 설치 창이 뜬다.

const string ServiceName = "HanilTimeGuard";
const string DisplayName = "한일 TimeGuard";
const string RunKeyName = "HanilTimeGuardAgent";
const string RunKeyPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";
const string Caption = "한일 TimeGuard 설치";

var installPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "HanilTimeGuard");

var dataPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "HanilTimeGuard");

var sourcePath = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
var selfFileName = Path.GetFileName(Environment.ProcessPath ?? "TimeGuard-Setup.exe");

// 여러 대를 한 번에 설치할 때 쓰는 명령줄 방식
var silent = args.Contains("/설치") || args.Contains("/install");
var silentRemove = args.Contains("/제거") || args.Contains("/uninstall");

SetupErrorReport.Install(Caption);

if (!SetupConsole.IsElevated())
{
    Message(
        "관리자 권한이 필요합니다.\n\n" +
        "이 파일을 마우스 오른쪽 버튼으로 누른 뒤\n" +
        "[관리자 권한으로 실행] 을 선택해 주세요.",
        MessageKind.Error);

    return 1;
}

if (silent || silentRemove)
{
    SetupConsole.AttachToParentConsole();
    var reporter = new ConsoleProgress();

    var outcome = silentRemove
        ? Remove(reporter, keepData: false)
        : Install(reporter, new SetupAnswers());

    Console.WriteLine();
    Console.WriteLine(outcome.Heading);

    return outcome.Success ? 0 : 1;
}

try
{
    return ShowWindow();
}
catch (Exception ex)
{
    // 창을 띄우는 중에 문제가 생기면 그냥 죽지 말고 원인을 알려 준다.
    SetupErrorReport.Show(ex);
    return 1;
}

// ================= 설치 창 =================

int ShowWindow()
{
    var installed = WindowsServiceSetup.Exists(ServiceName);

    using var wizard = new SetupWizard(Caption, "한일 TimeGuard")
    {
        Subheading = "직원 PC 설치 프로그램",
        CanRemove = installed,
        InstallButtonText = installed ? "다시 설치" : "설치",
        StatusIsGood = installed,
        StatusLine = installed
            ? $"이미 설치되어 있습니다.  (서비스: {DescribeStatus(WindowsServiceSetup.GetStatus(ServiceName))})"
            : "아직 설치되지 않았습니다.",
        WelcomeBody = BuildWelcomeText(installed),
        RemoveConfirmText =
            "제거하면 이 PC 는 더 이상 시간 제한을 받지 않습니다.\n\n" +
            "잠겨 있던 Windows 계정은 풀리고,\n" +
            "막아 두었던 원격 접속 설정도 되돌아갑니다.\n\n" +
            "정말 제거할까요?",
        InstallAction = Install,
        RemoveAction = progress => Remove(progress, keepData: true)
    };

    return wizard.Run();
}

string BuildWelcomeText(bool installed)
{
    var text = new StringBuilder();

    if (installed)
    {
        text.AppendLine("다시 설치하면 프로그램 파일이 최신으로 바뀝니다.");
        text.AppendLine("설정과 기록, 서버 등록 상태는 그대로 유지됩니다.");
        text.AppendLine();

        var settings = ServerSettings.Load();

        if (settings.IsConfigured)
        {
            text.AppendLine($"관리 서버   :  {settings.ServerUrl}");
            text.AppendLine($"등록 상태   :  {(settings.IsEnrolled ? "승인 완료" : "승인 대기 중")}");
            text.AppendLine($"확인 문자   :  {ServerSettings.DescribeFingerprint(settings.ClientId)}");
        }
        else
        {
            text.AppendLine("관리 서버   :  아직 찾지 못했습니다 (사내망에서 찾는 중)");
        }

        return text.ToString();
    }

    text.AppendLine("이 PC 에 사용 시간 제한을 설치합니다.");
    text.AppendLine();
    text.AppendLine("설치하면 이렇게 됩니다.");
    text.AppendLine();
    text.AppendLine("    ·  사내망에서 관리 서버를 스스로 찾습니다");
    text.AppendLine("    ·  관리자가 서버에서 [승인] 하면 시간표가 내려옵니다");
    text.AppendLine("    ·  승인 전에는 아무 제한도 걸리지 않습니다");
    text.AppendLine();
    text.AppendLine("등록 키나 서버 주소를 입력할 필요가 없습니다.");
    text.AppendLine("아래 [설치] 를 누르시면 됩니다.");

    return text.ToString();
}

// ================= 설치 =================

SetupOutcome Install(ISetupProgress progress, SetupAnswers answers)
{
    var embedded = Payload.IsEmbedded(Assembly.GetExecutingAssembly());

    if (!embedded && !File.Exists(Path.Combine(sourcePath, "TimeGuard.Service.exe")))
    {
        return new SetupOutcome(false, "설치 파일이 온전하지 않습니다",
            "설치에 필요한 파일이 들어 있지 않습니다.\r\n\r\n" +
            "파일을 다시 받아 주세요.\r\n" +
            "메신저로 주고받는 중에 파일이 깨졌을 수 있습니다.");
    }

    // --- 실행 중인 것 정리 ---
    progress.Step("실행 중인 프로그램을 정리합니다");

    if (WindowsServiceSetup.Exists(ServiceName))
    {
        WindowsServiceSetup.ResetAccessRights(ServiceName);

        if (!WindowsServiceSetup.Stop(ServiceName, out var stopError))
            progress.Warn($"서비스를 멈추지 못했습니다: {stopError}");
    }

    StopAgentProcesses();
    progress.Done("정리했습니다.");

    // --- 파일 풀기 ---
    if (embedded)
    {
        var count = Payload.Count(Assembly.GetExecutingAssembly());
        progress.Step($"프로그램 파일 {count}개를 풉니다");

        if (!Payload.Extract(Assembly.GetExecutingAssembly(), installPath, out var extractError))
        {
            return new SetupOutcome(false, "프로그램 파일을 풀지 못했습니다",
                extractError + "\r\n\r\n" +
                "백신 프로그램이 막고 있을 수 있습니다.\r\n잠시 끄고 다시 시도해 보세요.");
        }
    }
    else
    {
        // 개발 중이거나 폴더째 복사해 쓰는 경우
        progress.Step("프로그램을 설치합니다");

        if (!FileSetup.Copy(sourcePath, installPath, selfFileName, out var copyError))
        {
            return new SetupOutcome(false, "파일을 복사하지 못했습니다",
                copyError + "\r\n\r\n" +
                "백신 프로그램이 막고 있을 수 있습니다.\r\n잠시 끄고 다시 시도해 보세요.");
        }
    }

    progress.Done($"설치했습니다: {installPath}");

    // --- 자료 폴더 ---
    progress.Step("설정 폴더를 준비합니다");

    if (FileSetup.PrepareDataFolder(dataPath, allowUsersRead: true, out var dataError))
        progress.Done("일반 사용자는 읽기만 하도록 막았습니다.");
    else
        progress.Warn($"폴더 권한을 설정하지 못했습니다: {dataError}");

    EnsureInitialConfig(progress);

    // --- 서비스 등록 ---
    progress.Step("서비스를 등록합니다");

    var binaryPath = Path.Combine(installPath, "TimeGuard.Service.exe");

    if (!WindowsServiceSetup.Register(ServiceName, DisplayName,
            "허용된 시간대를 벗어나면 안내 후 설정된 조치를 수행합니다.", binaryPath, out var registerError))
    {
        return new SetupOutcome(false, "서비스를 등록하지 못했습니다", registerError);
    }

    progress.Done("등록했습니다.");

    // --- 보호 ---
    progress.Step("함부로 멈추거나 지울 수 없게 보호합니다");

    if (WindowsServiceSetup.Protect(ServiceName, out var protectError))
        progress.Done("서비스를 보호했습니다.");
    else
        progress.Warn($"서비스 보호에 실패했습니다: {protectError}");

    if (FileSetup.ProtectProgramFolder(installPath, out var folderError))
        progress.Done("프로그램 폴더를 보호했습니다.");
    else
        progress.Warn($"폴더 보호에 실패했습니다: {folderError}");

    // --- 알림 프로그램 자동 실행 ---
    progress.Step("알림 프로그램을 시작 프로그램에 등록합니다");
    RegisterAgentAutoStart(progress);
    progress.Done("등록했습니다.");

    // --- 시작 ---
    progress.Step("서비스를 시작합니다");

    if (!WindowsServiceSetup.Start(ServiceName, out var startError))
    {
        return new SetupOutcome(false, "서비스를 시작하지 못했습니다",
            startError + "\r\n\r\n" +
            "이벤트 뷰어의 [Windows 로그] → [응용 프로그램] 에서\r\n" +
            "자세한 원인을 확인할 수 있습니다.");
    }

    progress.Done("실행 중입니다.");

    // --- 안내 ---
    var settings = ServerSettings.Load();
    var fingerprint = ServerSettings.DescribeFingerprint(settings.EnsureClientId());

    var body = new StringBuilder();
    body.AppendLine("이 PC 가 사내망에서 관리 서버를 찾아 자기를 알립니다.");
    body.AppendLine();
    body.AppendLine("이제 관리자가 서버에서 승인해 주시면 됩니다.");
    body.AppendLine();
    body.AppendLine("    1.  서버 웹 화면에 접속합니다");
    body.AppendLine("    2.  [새 PC 승인] 에 이 PC 가 나타납니다");
    body.AppendLine("    3.  [승인] 을 누르면 끝입니다");
    body.AppendLine();
    body.AppendLine($"이 PC 이름   :  {Environment.MachineName}");
    body.AppendLine($"확인 문자    :  {fingerprint}");
    body.AppendLine();
    body.AppendLine("승인 화면에 같은 확인 문자가 보이면 이 PC 가 맞습니다.");

    return new SetupOutcome(true, "설치가 끝났습니다", body.ToString(),
        CopyText: $"{Environment.MachineName} / {fingerprint}",
        CopyButtonText: "PC 이름·확인 문자 복사");
}

// ================= 제거 =================

SetupOutcome Remove(ISetupProgress progress, bool keepData)
{
    progress.Step("잠겨 있던 Windows 계정을 풀어 줍니다");

    var unlocked = UnlockAccounts(progress);
    progress.Done(unlocked == 0 ? "잠긴 계정이 없습니다." : $"{unlocked}개 계정을 풀었습니다.");

    progress.Step("원격 접속 차단을 되돌립니다");
    RestoreRemoteAccess();
    progress.Done("되돌렸습니다.");

    progress.Step("서비스를 지웁니다");

    if (WindowsServiceSetup.Delete(ServiceName, out var deleteError))
        progress.Done("지웠습니다.");
    else
        progress.Warn($"서비스를 지우지 못했습니다: {deleteError}");

    StopAgentProcesses();

    progress.Step("시작 프로그램 등록을 해제합니다");

    try
    {
        using var key = Registry.LocalMachine.OpenSubKey(RunKeyPath, writable: true);
        key?.DeleteValue(RunKeyName, throwOnMissingValue: false);
        progress.Done("해제했습니다.");
    }
    catch (Exception ex)
    {
        progress.Warn($"해제하지 못했습니다: {ex.Message}");
    }

    // 서비스가 완전히 멈춰야 파일이 풀린다.
    Thread.Sleep(2000);

    progress.Step("프로그램 파일을 지웁니다");

    if (FileSetup.RemoveFolder(installPath, out var removeError))
        progress.Done("지웠습니다.");
    else
        progress.Warn($"일부 파일을 지우지 못했습니다: {removeError}");

    var body = new StringBuilder();
    body.AppendLine("이 PC 는 더 이상 시간 제한을 받지 않습니다.");
    body.AppendLine();

    if (keepData)
    {
        body.AppendLine("설정과 기록은 남겨 두었습니다.");
        body.AppendLine($"    {dataPath}");
        body.AppendLine();
        body.AppendLine("필요 없으시면 위 폴더를 직접 지우시면 됩니다.");
    }
    else
    {
        progress.Step("설정과 기록을 지웁니다");

        if (FileSetup.RemoveFolder(dataPath, out var dataRemoveError))
            progress.Done("지웠습니다.");
        else
            progress.Warn($"지우지 못했습니다: {dataRemoveError}");
    }

    body.AppendLine();
    body.AppendLine("서버의 [PC 목록] 에서도 이 PC 를 지워 주십시오.");

    return new SetupOutcome(true, "제거가 끝났습니다", body.ToString());
}

// ================= 도우미 =================

string DescribeStatus(System.ServiceProcess.ServiceControllerStatus? status) => status switch
{
    System.ServiceProcess.ServiceControllerStatus.Running => "실행 중",
    System.ServiceProcess.ServiceControllerStatus.Stopped => "멈춤",
    System.ServiceProcess.ServiceControllerStatus.StartPending => "시작하는 중",
    System.ServiceProcess.ServiceControllerStatus.StopPending => "멈추는 중",
    null => "설치되지 않음",
    _ => status.ToString() ?? "알 수 없음"
};

void EnsureInitialConfig(ISetupProgress progress)
{
    try
    {
        var configPath = Path.Combine(dataPath, "config.json");
        if (File.Exists(configPath)) return;

        // 설정이 끝나기 전에는 아무도 제한받지 않도록 감시를 꺼 둔 채 만든다.
        new ConfigStore(configPath).Save(GuardConfig.CreateInitial(), "설치");
    }
    catch (Exception ex)
    {
        progress.Warn($"기본 설정을 만들지 못했습니다: {ex.Message}");
    }
}

void RegisterAgentAutoStart(ISetupProgress progress)
{
    try
    {
        using var key = Registry.LocalMachine.CreateSubKey(RunKeyPath);
        key?.SetValue(RunKeyName, $"\"{Path.Combine(installPath, "TimeGuard.Agent.exe")}\"", RegistryValueKind.String);
    }
    catch (Exception ex)
    {
        progress.Warn($"시작 프로그램에 등록하지 못했습니다: {ex.Message}");
    }
}

static void StopAgentProcesses()
{
    try
    {
        foreach (var process in System.Diagnostics.Process.GetProcessesByName("TimeGuard.Agent"))
        {
            using (process)
            {
                try
                {
                    process.Kill();
                    process.WaitForExit(5000);
                }
                catch (Exception)
                {
                    // 이미 끝났거나 접근할 수 없는 프로세스는 건너뛴다.
                }
            }
        }
    }
    catch (Exception)
    {
        // 정리에 실패해도 설치는 계속한다.
    }
}

int UnlockAccounts(ISetupProgress progress)
{
    var path = Path.Combine(dataPath, "locked-accounts.json");
    if (!File.Exists(path)) return 0;

    var count = 0;

    try
    {
        var locked = System.Text.Json.JsonSerializer.Deserialize<List<LockedAccountEntry>>(
            File.ReadAllText(path));

        foreach (var entry in locked ?? new List<LockedAccountEntry>())
        {
            if (string.IsNullOrWhiteSpace(entry.UserName)) continue;

            var startInfo = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "net",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            startInfo.ArgumentList.Add("user");
            startInfo.ArgumentList.Add(entry.UserName);
            startInfo.ArgumentList.Add("/active:yes");

            using var process = System.Diagnostics.Process.Start(startInfo);
            process?.WaitForExit(10000);

            if (process?.ExitCode == 0) count++;
        }

        File.Delete(path);
    }
    catch (Exception ex)
    {
        progress.Warn($"잠긴 계정을 푸는 중 문제가 있었습니다: {ex.Message}");
        progress.Note("직접 풀려면: net user 계정이름 /active:yes");
    }

    return count;
}

static void RestoreRemoteAccess()
{
    try
    {
        using var backup = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\HanilTimeGuard", writable: true);
        if (backup?.GetValue("RemoteAccessOriginal") is not int original) return;

        using var terminalServer = Registry.LocalMachine.OpenSubKey(
            @"SYSTEM\CurrentControlSet\Control\Terminal Server", writable: true);

        terminalServer?.SetValue("fDenyTSConnections", original, RegistryValueKind.DWord);
        backup.DeleteValue("RemoteAccessOriginal", throwOnMissingValue: false);
    }
    catch (Exception)
    {
        // 되돌리지 못해도 제거는 계속한다.
    }
}

// 창을 띄우기 전에 쓸 수 있는 간단한 알림 상자
static void Message(string text, MessageKind kind)
{
    const uint MB_OK = 0x0;
    uint icon = kind switch
    {
        MessageKind.Error => 0x10,
        MessageKind.Warning => 0x30,
        _ => 0x40
    };

    MessageBoxW(IntPtr.Zero, text, "한일 TimeGuard 설치", MB_OK | icon);
}

[DllImport("user32.dll", CharSet = CharSet.Unicode)]
static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

internal enum MessageKind { Info, Warning, Error }

internal sealed class LockedAccountEntry
{
    public string UserName { get; set; } = string.Empty;
}

/// <summary>무인 설치용. 창 없이 명령 창에 진행 상황을 쓴다.</summary>
internal sealed class ConsoleProgress : ISetupProgress
{
    public void Step(string text) => Console.WriteLine($"   {text}");
    public void Done(string text) => Console.WriteLine($"[완료] {text}");
    public void Note(string text) => Console.WriteLine($"       {text}");
    public void Warn(string text) => Console.WriteLine($"[주의] {text}");
}
