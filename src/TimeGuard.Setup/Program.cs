using System.Runtime.Versioning;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.SetupKit;
using Microsoft.Win32;

[assembly: SupportedOSPlatform("windows")]

// 직원 PC 용 설치 프로그램.
// 더블클릭하면 Windows 가 관리자 권한을 물어보고, 그 뒤로는 알아서 진행된다.

const string ServiceName = "HanilTimeGuard";
const string DisplayName = "한일 TimeGuard";
const string RunKeyName = "HanilTimeGuardAgent";
const string RunKeyPath = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";

var installPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "HanilTimeGuard");

var dataPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "HanilTimeGuard");

var sourcePath = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
var selfFileName = Path.GetFileName(Environment.ProcessPath ?? "TimeGuard-설치.exe");

SetupConsole.Prepare("한일 TimeGuard 설치");

// 명령줄로도 쓸 수 있게 한다. 여러 대를 자동으로 설치할 때 쓴다.
var silent = args.Contains("/설치") || args.Contains("/install");
var uninstall = args.Contains("/제거") || args.Contains("/uninstall");

if (!SetupConsole.IsElevated())
{
    SetupConsole.Error("관리자 권한이 필요합니다.");
    SetupConsole.Dim("이 파일을 마우스 오른쪽 클릭 후 [관리자 권한으로 실행] 을 선택해 주세요.");
    SetupConsole.WaitForKey();
    return 1;
}

if (uninstall) return Uninstall(confirm: false);
if (silent) return Install(quiet: true);

return ShowMenu();

// ================= 메뉴 =================

int ShowMenu()
{
    while (true)
    {
        Console.Clear();
        SetupConsole.Banner("한일 TimeGuard", "직원 PC 설치 프로그램");

        var installed = WindowsServiceSetup.Exists(ServiceName);

        if (installed)
        {
            var status = WindowsServiceSetup.GetStatus(ServiceName);
            SetupConsole.Ok($"이미 설치되어 있습니다. (서비스 상태: {DescribeStatus(status)})");
            DescribeServerLink();
        }
        else
        {
            SetupConsole.Info("아직 설치되지 않았습니다.");
        }

        var choice = installed
            ? SetupConsole.Choose("다시 설치 (프로그램 갱신)", "현재 상태 보기", "제거")
            : SetupConsole.Choose("설치", "현재 상태 보기");

        switch (choice)
        {
            case 0:
                return 0;

            case 1:
                Install(quiet: false);
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;

            case 2:
                ShowStatus();
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;

            case 3:
                Uninstall(confirm: true);
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;
        }
    }
}

// ================= 설치 =================

int Install(bool quiet)
{
    SetupConsole.Blank();
    SetupConsole.Banner("설치를 시작합니다", "잠시만 기다려 주세요");

    if (!File.Exists(Path.Combine(sourcePath, "TimeGuard.Service.exe")))
    {
        SetupConsole.Error("설치 파일을 찾을 수 없습니다.");
        SetupConsole.Dim($"이 프로그램이 있는 폴더: {sourcePath}");
        SetupConsole.Dim("압축을 푼 폴더 안에서 실행해 주세요.");
        if (!quiet) SetupConsole.WaitForKey();
        return 1;
    }

    // --- 실행 중인 것 정리 ---
    SetupConsole.Step("실행 중인 프로그램을 정리합니다");

    if (WindowsServiceSetup.Exists(ServiceName))
    {
        WindowsServiceSetup.ResetAccessRights(ServiceName);

        if (!WindowsServiceSetup.Stop(ServiceName, out var stopError))
            SetupConsole.Warn($"서비스를 멈추지 못했습니다: {stopError}");
    }

    StopAgentProcesses();
    SetupConsole.Ok("정리했습니다.");

    // --- 파일 복사 ---
    SetupConsole.Step($"프로그램을 설치합니다: {installPath}");

    if (!FileSetup.Copy(sourcePath, installPath, selfFileName, out var copyError))
    {
        SetupConsole.Error($"파일을 복사하지 못했습니다: {copyError}");
        if (!quiet) SetupConsole.WaitForKey();
        return 1;
    }

    SetupConsole.Ok("복사를 마쳤습니다.");

    // --- 자료 폴더 ---
    SetupConsole.Step("설정 폴더를 준비합니다");

    if (FileSetup.PrepareDataFolder(dataPath, allowUsersRead: true, out var dataError))
        SetupConsole.Ok("일반 사용자는 읽기만 할 수 있도록 설정했습니다.");
    else
        SetupConsole.Warn($"폴더 권한을 설정하지 못했습니다: {dataError}");

    EnsureInitialConfig();

    // --- 서비스 등록 ---
    SetupConsole.Step("서비스를 등록합니다");

    var binaryPath = Path.Combine(installPath, "TimeGuard.Service.exe");

    if (!WindowsServiceSetup.Register(ServiceName, DisplayName,
            "허용된 시간대를 벗어나면 안내 후 설정된 조치를 수행합니다.", binaryPath, out var registerError))
    {
        SetupConsole.Error($"서비스를 등록하지 못했습니다: {registerError}");
        if (!quiet) SetupConsole.WaitForKey();
        return 1;
    }

    SetupConsole.Ok("등록했습니다.");

    // --- 보호 ---
    SetupConsole.Step("함부로 멈추거나 지울 수 없게 보호합니다");

    if (WindowsServiceSetup.Protect(ServiceName, out var protectError))
        SetupConsole.Ok("서비스를 보호했습니다.");
    else
        SetupConsole.Warn($"서비스 보호에 실패했습니다: {protectError}");

    if (FileSetup.ProtectProgramFolder(installPath, out var folderError))
        SetupConsole.Ok("프로그램 폴더를 보호했습니다.");
    else
        SetupConsole.Warn($"폴더 보호에 실패했습니다: {folderError}");

    // --- 알림 프로그램 자동 실행 ---
    SetupConsole.Step("알림 프로그램을 시작 프로그램에 등록합니다");
    RegisterAgentAutoStart();
    SetupConsole.Ok("등록했습니다.");

    // --- 시작 ---
    SetupConsole.Step("서비스를 시작합니다");

    if (!WindowsServiceSetup.Start(ServiceName, out var startError))
    {
        SetupConsole.Error($"서비스를 시작하지 못했습니다: {startError}");
        SetupConsole.Dim("이벤트 뷰어의 응용 프로그램 로그를 확인해 주세요.");
        if (!quiet) SetupConsole.WaitForKey();
        return 1;
    }

    SetupConsole.Ok("실행 중입니다.");

    // --- 안내 ---
    SetupConsole.Blank();
    SetupConsole.Banner("설치가 끝났습니다", "이제 서버에서 이 PC 를 승인해 주세요");

    Console.WriteLine("  이 PC 가 사내망에서 관리 서버를 찾아 자기를 알립니다.");
    Console.WriteLine();
    Console.WriteLine("  관리자가 할 일:");
    Console.WriteLine("    1. 서버 웹 화면에 접속합니다");
    Console.WriteLine("    2. [새 PC 승인] 화면에 이 PC 가 나타납니다");
    Console.WriteLine("    3. [승인] 을 누르면 끝입니다");
    SetupConsole.Blank();

    var settings = ServerSettings.Load();
    var fingerprint = ServerSettings.DescribeFingerprint(settings.EnsureClientId());

    Console.WriteLine($"  이 PC 이름   : {Environment.MachineName}");
    Console.WriteLine($"  확인 문자    : {fingerprint}");
    SetupConsole.Dim("  (승인 화면에서 같은 값이 보이면 이 PC 가 맞습니다)");

    SetupConsole.Blank();
    SetupConsole.Dim($"  설정 파일: {Path.Combine(dataPath, "config.json")}");
    SetupConsole.Dim($"  기록 파일: {Path.Combine(dataPath, "timeguard.log")}");

    if (quiet) return 0;

    SetupConsole.Blank();
    return 0;
}

// ================= 제거 =================

int Uninstall(bool confirm)
{
    SetupConsole.Blank();
    SetupConsole.Banner("제거", "이 PC 에서 TimeGuard 를 지웁니다");

    if (confirm)
    {
        SetupConsole.Warn("제거하면 이 PC 는 더 이상 시간 제한을 받지 않습니다.");
        SetupConsole.Blank();

        if (!SetupConsole.Confirm("정말 제거할까요?", defaultYes: false))
        {
            SetupConsole.Info("취소했습니다.");
            return 0;
        }
    }

    SetupConsole.Blank();

    // --- 잠긴 계정 풀기 ---
    SetupConsole.Step("잠겨 있던 Windows 계정을 풀어 줍니다");

    var unlocked = UnlockAccounts();
    SetupConsole.Ok(unlocked == 0 ? "잠긴 계정이 없습니다." : $"{unlocked}개 계정을 풀었습니다.");

    // --- 원격 접속 차단 해제 ---
    SetupConsole.Step("원격 접속 차단을 되돌립니다");
    RestoreRemoteAccess();
    SetupConsole.Ok("되돌렸습니다.");

    // --- 서비스 삭제 ---
    SetupConsole.Step("서비스를 지웁니다");

    if (WindowsServiceSetup.Delete(ServiceName, out var deleteError))
        SetupConsole.Ok("지웠습니다.");
    else
        SetupConsole.Warn($"서비스를 지우지 못했습니다: {deleteError}");

    StopAgentProcesses();

    // --- 시작 프로그램 해제 ---
    SetupConsole.Step("시작 프로그램 등록을 해제합니다");

    try
    {
        using var key = Registry.LocalMachine.OpenSubKey(RunKeyPath, writable: true);
        key?.DeleteValue(RunKeyName, throwOnMissingValue: false);
        SetupConsole.Ok("해제했습니다.");
    }
    catch (Exception ex)
    {
        SetupConsole.Warn($"해제하지 못했습니다: {ex.Message}");
    }

    Thread.Sleep(2000);

    // --- 파일 삭제 ---
    SetupConsole.Step("프로그램 파일을 지웁니다");

    if (FileSetup.RemoveFolder(installPath, out var removeError))
        SetupConsole.Ok("지웠습니다.");
    else
        SetupConsole.Warn($"일부 파일을 지우지 못했습니다: {removeError}");

    // --- 설정 ---
    SetupConsole.Blank();

    var keepData = confirm && SetupConsole.Confirm("설정과 기록을 남겨 둘까요?", defaultYes: false);

    if (!keepData)
    {
        SetupConsole.Step("설정과 기록을 지웁니다");

        if (FileSetup.RemoveFolder(dataPath, out var dataRemoveError))
            SetupConsole.Ok("지웠습니다.");
        else
            SetupConsole.Warn($"지우지 못했습니다: {dataRemoveError}");
    }
    else
    {
        SetupConsole.Info($"설정과 기록은 그대로 두었습니다: {dataPath}");
    }

    SetupConsole.Blank();
    SetupConsole.Banner("제거가 끝났습니다", "");

    return 0;
}

// ================= 상태 =================

void ShowStatus()
{
    SetupConsole.Blank();
    SetupConsole.Banner("현재 상태", Environment.MachineName);

    var status = WindowsServiceSetup.GetStatus(ServiceName);
    Console.WriteLine($"  서비스      : {DescribeStatus(status)}");

    DescribeServerLink();

    var configPath = Path.Combine(dataPath, "config.json");

    if (File.Exists(configPath))
    {
        var config = new ConfigStore(configPath).Load(out _);

        Console.WriteLine($"  감시        : {(config.Enabled ? "켜짐" : "꺼짐")}");
        Console.WriteLine($"  시간 초과 시: {DescribeAction(config.Action)}");
    }
    else
    {
        Console.WriteLine("  설정        : 아직 없습니다.");
    }

    SetupConsole.Blank();
    SetupConsole.Dim($"  자세한 상태: \"{Path.Combine(installPath, "TimeGuard.Admin.exe")}\" status");
}

void DescribeServerLink()
{
    var settings = ServerSettings.Load();

    if (!settings.IsConfigured)
    {
        Console.WriteLine("  관리 서버   : 아직 찾지 못했습니다 (사내망에서 찾는 중)");
        return;
    }

    Console.WriteLine($"  관리 서버   : {settings.ServerUrl}");
    Console.WriteLine($"  등록 상태   : {(settings.IsEnrolled ? "승인 완료" : "승인 대기 중")}");
    Console.WriteLine($"  확인 문자   : {ServerSettings.DescribeFingerprint(settings.ClientId)}");
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

static string DescribeAction(GuardAction action) => action switch
{
    GuardAction.Shutdown => "전원 차단",
    GuardAction.AccountLock => "계정 잠금",
    GuardAction.LogOff => "로그오프",
    GuardAction.Lock => "화면 잠금",
    _ => action.ToString()
};

void EnsureInitialConfig()
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
        SetupConsole.Warn($"기본 설정을 만들지 못했습니다: {ex.Message}");
    }
}

void RegisterAgentAutoStart()
{
    try
    {
        using var key = Registry.LocalMachine.CreateSubKey(RunKeyPath);
        key?.SetValue(RunKeyName, $"\"{Path.Combine(installPath, "TimeGuard.Agent.exe")}\"", RegistryValueKind.String);
    }
    catch (Exception ex)
    {
        SetupConsole.Warn($"시작 프로그램에 등록하지 못했습니다: {ex.Message}");
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

int UnlockAccounts()
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
        SetupConsole.Warn($"잠긴 계정을 푸는 중 문제가 있었습니다: {ex.Message}");
        SetupConsole.Dim("직접 풀려면: net user 계정이름 /active:yes");
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

internal sealed class LockedAccountEntry
{
    public string UserName { get; set; } = string.Empty;
}
