using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.SetupKit;
using Hanil.TimeGuard.SetupKit.Ui;

[assembly: SupportedOSPlatform("windows")]

// 관리 서버용 설치 프로그램.
// 사무실 PC 한 대에서 더블클릭하면 서버가 준비된다.

const string ServiceName = "HanilTimeGuardServer";
const string DisplayName = "한일 TimeGuard 관리 서버";
const string FirewallRuleName = "한일 TimeGuard 관리 서버";
const string DiscoveryRuleName = "한일 TimeGuard 서버 찾기";
const string Caption = "한일 TimeGuard 관리 서버 설치";
const int DefaultHttpsPort = 8443;
const int DefaultHttpPort = 8080;

var installPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "HanilTimeGuardServer");

var dataPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "HanilTimeGuardServer");

var sourcePath = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
var selfFileName = Path.GetFileName(Environment.ProcessPath ?? "TimeGuard-Server-Setup.exe");

SetupErrorReport.Install(Caption);

if (!SetupConsole.IsElevated())
{
    MessageBoxW(IntPtr.Zero,
        "관리자 권한이 필요합니다.\n\n" +
        "이 파일을 마우스 오른쪽 버튼으로 누른 뒤\n" +
        "[관리자 권한으로 실행] 을 선택해 주세요.",
        Caption, 0x10);

    return 1;
}

try
{
    return ShowWindow();
}
catch (Exception ex)
{
    SetupErrorReport.Show(ex);
    return 1;
}

// ================= 설치 창 =================

int ShowWindow()
{
    var installed = WindowsServiceSetup.Exists(ServiceName);

    using var wizard = new SetupWizard(Caption, "한일 TimeGuard 관리 서버")
    {
        Subheading = "사무실 PC 한 대에 설치합니다",
        CanRemove = installed,
        InstallButtonText = installed ? "다시 설치" : "설치",
        StatusIsGood = installed,
        StatusLine = installed
            ? $"이미 설치되어 있습니다.  (서비스: {DescribeStatus(WindowsServiceSetup.GetStatus(ServiceName))})"
            : "아직 설치되지 않았습니다.",
        WelcomeBody = BuildWelcomeText(installed),
        OptionsHeading = "설치 전에 두 가지만 정합니다",
        RemoveConfirmText =
            "서버를 지워도 직원 PC 의 제한은 그대로 유지됩니다.\n" +
            "직원 PC 의 제한을 풀려면 각 PC 에서 따로 제거하셔야 합니다.\n\n" +
            "설정과 기록(데이터베이스)은 남겨 둡니다.\n\n" +
            "정말 제거할까요?",
        InstallAction = Install,
        RemoveAction = Remove
    };

    wizard.Choices.Add(new SetupChoice(
        "https",
        "통신을 암호화합니다 (권장)",
        "켜 두면 사내망에서 누가 엿보아도 비밀번호를 알아낼 수 없습니다.",
        DefaultOn: true));

    wizard.TextFields.Add(new SetupTextField(
        "port",
        "접속 포트",
        DefaultHttpsPort.ToString(),
        "그대로 두셔도 됩니다. (암호화 8443 / 암호화 안 함 8080)",
        NumbersOnly: true));

    return wizard.Run();
}

string BuildWelcomeText(bool installed)
{
    var text = new StringBuilder();

    if (installed)
    {
        text.AppendLine("다시 설치하면 프로그램 파일이 최신으로 바뀝니다.");
        text.AppendLine("설정과 기록, 인증서는 그대로 유지됩니다.");
        text.AppendLine();

        var address = CurrentAddress();

        if (address is not null)
        {
            text.AppendLine("관리 화면 주소");
            text.AppendLine($"    {address}");
        }

        return text.ToString();
    }

    text.AppendLine("직원 PC 들의 사용 시간표를 여기서 한꺼번에 관리합니다.");
    text.AppendLine();
    text.AppendLine("설치하면 이렇게 됩니다.");
    text.AppendLine();
    text.AppendLine("    ·  웹 화면에서 시간표를 정하고 연장 요청을 승인합니다");
    text.AppendLine("    ·  직원 PC 가 사내망에서 이 서버를 알아서 찾습니다");
    text.AppendLine("    ·  사내망에서만 접속되도록 방화벽을 엽니다");
    text.AppendLine();
    text.AppendLine("이 PC 는 업무 시간 동안 켜 두셔야 합니다.");
    text.AppendLine("꺼져 있어도 직원 PC 의 제한은 그대로 유지됩니다.");

    return text.ToString();
}

// ================= 설치 =================

SetupOutcome Install(ISetupProgress progress, SetupAnswers answers)
{
    var embedded = Payload.IsEmbedded(Assembly.GetExecutingAssembly());

    if (!embedded && !File.Exists(Path.Combine(sourcePath, "TimeGuard.Server.exe")))
    {
        return new SetupOutcome(false, "설치 파일이 온전하지 않습니다",
            "설치에 필요한 파일이 들어 있지 않습니다.\r\n\r\n" +
            "파일을 다시 받아 주세요.\r\n" +
            "메신저로 주고받는 중에 파일이 깨졌을 수 있습니다.");
    }

    var useHttps = answers.Choice("https", fallback: true);
    var port = answers.Number("port", useHttps ? DefaultHttpsPort : DefaultHttpPort);

    if (port < 1 || port > 65535)
    {
        port = useHttps ? DefaultHttpsPort : DefaultHttpPort;
        progress.Warn($"포트를 알아볼 수 없어 기본값 {port} 을(를) 씁니다.");
    }

    // --- 기존 서버 정리 ---
    progress.Step("실행 중인 서버를 정리합니다");

    if (WindowsServiceSetup.Exists(ServiceName))
    {
        if (!WindowsServiceSetup.Stop(ServiceName, out var stopError))
            progress.Warn($"서버를 멈추지 못했습니다: {stopError}");
    }

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
    // 데이터베이스에 관리자 비밀번호와 장비 토큰이 들어 있으므로 일반 사용자는 접근할 수 없게 한다.
    progress.Step("자료 폴더 권한을 설정합니다");

    if (FileSetup.PrepareDataFolder(dataPath, allowUsersRead: false, out var dataError))
        progress.Done("관리자만 접근할 수 있게 했습니다.");
    else
        progress.Warn($"폴더 권한을 설정하지 못했습니다: {dataError}");

    // --- 암호화 설정 ---
    var scheme = "http";

    if (useHttps)
    {
        progress.Step("통신 암호화를 준비합니다");

        if (ConfigureHttps(port, out var certError))
        {
            scheme = "https";
            progress.Done("인증서를 만들고 암호화를 켰습니다.");
        }
        else
        {
            progress.Warn($"암호화를 켜지 못했습니다: {certError}");
            progress.Warn("암호화 없이 설치를 계속합니다.");
            ConfigureHttp(port);
        }
    }
    else
    {
        progress.Step($"접속 포트를 설정합니다: {port}");
        ConfigureHttp(port);
        progress.Done("설정했습니다.");
    }

    // --- 서비스 등록 ---
    progress.Step("서비스를 등록합니다");

    var binaryPath = Path.Combine(installPath, "TimeGuard.Server.exe");

    if (!WindowsServiceSetup.Register(ServiceName, DisplayName,
            "직원 PC 의 사용 시간표를 관리하고 연장 요청을 받습니다.", binaryPath, out var registerError))
    {
        return new SetupOutcome(false, "서비스를 등록하지 못했습니다", registerError);
    }

    progress.Done("등록했습니다.");

    // --- 방화벽 ---
    progress.Step("사내망에서 접속할 수 있게 방화벽을 엽니다");

    if (NetworkSetup.OpenPort($"{FirewallRuleName} ({port})", port, "TCP", out var firewallError))
        progress.Done($"포트 {port} 을(를) 열었습니다. (사내망에서만)");
    else
        progress.Warn($"방화벽을 열지 못했습니다: {firewallError}");

    // 직원 PC 가 이 서버를 찾을 수 있게 하는 통로.
    if (NetworkSetup.OpenPort(DiscoveryRuleName, 8765, "UDP", out var discoveryError))
        progress.Done("직원 PC 가 이 서버를 찾을 수 있게 했습니다.");
    else
        progress.Warn($"서버 찾기 통로를 열지 못했습니다: {discoveryError}");

    // --- 시작 ---
    progress.Step("서버를 시작합니다");

    if (!WindowsServiceSetup.Start(ServiceName, out var startError))
    {
        return new SetupOutcome(false, "서버를 시작하지 못했습니다",
            startError + "\r\n\r\n" +
            "이벤트 뷰어의 [Windows 로그] → [응용 프로그램] 에서\r\n" +
            "자세한 원인을 확인할 수 있습니다.");
    }

    // 최초 설정 정보가 만들어질 때까지 잠시 기다린다.
    Thread.Sleep(4000);
    progress.Done("실행 중입니다.");

    // --- 직원 PC 가 실제로 찾을 수 있는지 확인 ---
    //
    // 직원 PC 와 똑같은 신호를 사내망에 보내 본다.
    // 답이 오지 않으면 방화벽이나 네트워크 설정 문제이며,
    // 그대로 두면 직원 PC 에서 아무리 설치해도 서버 화면에 나타나지 않는다.
    // 나중에 원인을 찾느라 헤매지 않도록 지금 확인해서 알려 준다.
    progress.Step("직원 PC 가 이 서버를 찾을 수 있는지 확인합니다");

    var discoverable = CanBeDiscovered();

    if (discoverable)
        progress.Done("찾을 수 있습니다.");
    else
        progress.Warn("이 PC 에서조차 찾지 못했습니다. 아래 안내를 확인해 주세요.");

    // --- 안내 ---
    var address = NetworkSetup.FindLocalAddress();
    var localUrl = $"{scheme}://localhost:{port}";
    var lanUrl = address is null ? null : $"{scheme}://{address}:{port}";

    var body = new StringBuilder();
    body.AppendLine("관리 화면 주소");
    body.AppendLine($"    이 PC 에서      :  {localUrl}");
    if (lanUrl is not null)
        body.AppendLine($"    다른 PC 에서   :  {lanUrl}");
    body.AppendLine();

    var (loginId, loginPassword) = ReadLoginInfo();

    if (loginPassword is not null)
    {
        body.AppendLine("최초 로그인");
        body.AppendLine($"    아이디          :  {loginId}");
        body.AppendLine($"    임시 비밀번호  :  {loginPassword}");
        body.AppendLine();
        body.AppendLine("로그인한 뒤 [설정] 에서 비밀번호를 꼭 바꾸십시오.");
    }
    else
    {
        body.AppendLine("이미 비밀번호를 바꾸신 상태입니다. 쓰시던 비밀번호로 로그인하십시오.");
    }

    body.AppendLine();
    body.AppendLine("다음 순서");
    body.AppendLine("    1.  [기본 시간표] 에서 허용 시간대를 정합니다");
    body.AppendLine("    2.  직원 PC 에서 설치 프로그램을 실행합니다");
    body.AppendLine("    3.  [새 PC 승인] 에 나타나면 [승인] 을 누릅니다");

    if (!discoverable)
    {
        body.AppendLine();
        body.AppendLine("──────────────────────────────────────────");
        body.AppendLine("주의:  직원 PC 가 이 서버를 찾지 못할 수 있습니다.");
        body.AppendLine();
        body.AppendLine("이 PC 에서 서버 찾기 신호를 보내 봤지만 답이 오지 않았습니다.");
        body.AppendLine("대개 Windows 가 사무실 랜을 [공용 네트워크] 로 잡아 둔 탓입니다.");
        body.AppendLine("방화벽 규칙은 사내망에만 열리므로 그때는 적용되지 않습니다.");
        body.AppendLine();
        body.AppendLine("고치는 방법");
        body.AppendLine("    [설정] → [네트워크 및 인터넷] → 연결된 네트워크를 누르고");
        body.AppendLine("    네트워크 프로필을 [개인] 으로 바꾸십시오.");
        body.AppendLine();
        body.AppendLine("바꾼 뒤 이 설치 프로그램을 다시 실행해 [다시 설치] 를 누르면");
        body.AppendLine("여기서 다시 확인해 드립니다.");
    }

    if (scheme == "https")
    {
        body.AppendLine();
        body.AppendLine("다른 PC 에서 인증서 경고가 뜨면 [고급] → [계속] 을 누르시면 됩니다.");
        body.AppendLine("경고를 없애려면 아래 파일을 그 PC 에 설치하십시오.");
        body.AppendLine($"    {Path.Combine(installPath, "server-certificate.cer")}");
    }

    var copyText = new StringBuilder();
    copyText.AppendLine($"관리 화면: {lanUrl ?? localUrl}");
    if (loginPassword is not null)
    {
        copyText.AppendLine($"아이디: {loginId}");
        copyText.AppendLine($"임시 비밀번호: {loginPassword}");
    }

    return new SetupOutcome(true, "설치가 끝났습니다", body.ToString(),
        CopyText: copyText.ToString(),
        CopyButtonText: "주소·비밀번호 복사",
        OpenUrl: localUrl,
        OpenButtonText: "관리 화면 열기");
}

// ================= 제거 =================

SetupOutcome Remove(ISetupProgress progress)
{
    progress.Step("서비스를 지웁니다");

    if (WindowsServiceSetup.Delete(ServiceName, out var deleteError))
        progress.Done("지웠습니다.");
    else
        progress.Warn($"서비스를 지우지 못했습니다: {deleteError}");

    progress.Step("방화벽 규칙을 지웁니다");

    foreach (var port in new[] { DefaultHttpsPort, DefaultHttpPort })
        NetworkSetup.ClosePort($"{FirewallRuleName} ({port})");

    NetworkSetup.ClosePort(DiscoveryRuleName);
    progress.Done("지웠습니다.");

    // 서버가 완전히 멈춰야 파일이 풀린다.
    Thread.Sleep(2000);

    progress.Step("프로그램 파일을 지웁니다");

    if (FileSetup.RemoveFolder(installPath, out var removeError))
        progress.Done("지웠습니다.");
    else
        progress.Warn($"일부 파일을 지우지 못했습니다: {removeError}");

    var body = new StringBuilder();
    body.AppendLine("설정과 기록은 남겨 두었습니다.");
    body.AppendLine($"    {dataPath}");
    body.AppendLine();
    body.AppendLine("다시 설치하면 이 자료를 그대로 이어서 씁니다.");
    body.AppendLine("완전히 지우시려면 위 폴더를 직접 삭제하십시오.");
    body.AppendLine();
    body.AppendLine("주의: 서버를 지워도 직원 PC 의 제한은 그대로 유지됩니다.");
    body.AppendLine("각 PC 에서 TimeGuard-Setup.exe 로 제거하셔야 풀립니다.");

    return new SetupOutcome(true, "제거가 끝났습니다", body.ToString());
}

// ================= 설정 파일 =================

void ConfigureHttp(int port)
{
    UpdateSettings(endpoints =>
    {
        endpoints["Http"] = new JsonObject { ["Url"] = $"http://0.0.0.0:{port}" };
    });
}

bool ConfigureHttps(int port, out string detail)
{
    detail = string.Empty;

    try
    {
        var certificatePath = Path.Combine(installPath, "server-cert.pfx");
        var publicPath = Path.Combine(installPath, "server-certificate.cer");

        // 이미 쓰던 인증서가 있으면 그대로 쓴다.
        // 새로 만들면 직원 PC 들이 기억해 둔 것과 달라져 모두 다시 등록해야 한다.
        var reuse = File.Exists(certificatePath) && TryReadPassword(out _);

        string password;
        X509Certificate2 certificate;

        if (reuse)
        {
            password = ReadPassword();
            certificate = new X509Certificate2(certificatePath, password,
                X509KeyStorageFlags.Exportable | X509KeyStorageFlags.MachineKeySet);
        }
        else
        {
            certificate = NetworkSetup.CreateServerCertificate(NetworkSetup.CollectHostNames());
            password = Convert.ToBase64String(RandomNumberGenerator.GetBytes(24));

            File.WriteAllBytes(certificatePath, certificate.Export(X509ContentType.Pfx, password));
            File.WriteAllBytes(publicPath, certificate.Export(X509ContentType.Cert));

            SavePassword(password);
        }

        NetworkSetup.TrustOnThisMachine(certificate);
        certificate.Dispose();

        UpdateSettings(endpoints =>
        {
            endpoints["Https"] = new JsonObject
            {
                ["Url"] = $"https://0.0.0.0:{port}",
                ["Certificate"] = new JsonObject
                {
                    ["Path"] = certificatePath,
                    ["Password"] = password
                }
            };
        });

        ProtectSettingsFile();
        return true;
    }
    catch (Exception ex)
    {
        detail = ex.Message;
        return false;
    }
}

void UpdateSettings(Action<JsonObject> configureEndpoints)
{
    var settingsPath = Path.Combine(installPath, "appsettings.json");

    var root = File.Exists(settingsPath)
        ? JsonNode.Parse(File.ReadAllText(settingsPath))?.AsObject() ?? new JsonObject()
        : new JsonObject();

    var kestrel = root["Kestrel"]?.AsObject() ?? new JsonObject();

    // 이전에 쓰던 통신 방식이 남아 있으면 지운다. 둘이 겹치면 서버가 뜨지 않는다.
    var endpoints = new JsonObject();
    configureEndpoints(endpoints);

    kestrel["Endpoints"] = endpoints;
    root["Kestrel"] = kestrel;

    File.WriteAllText(settingsPath,
        root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
}

void ProtectSettingsFile()
{
    // 설정 파일에 인증서 비밀번호가 들어 있으므로 관리자만 읽게 한다.
    try
    {
        var settingsPath = Path.Combine(installPath, "appsettings.json");
        var file = new FileInfo(settingsPath);
        var security = file.GetAccessControl();

        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);

        foreach (var sid in new[]
                 {
                     System.Security.Principal.WellKnownSidType.LocalSystemSid,
                     System.Security.Principal.WellKnownSidType.BuiltinAdministratorsSid
                 })
        {
            security.AddAccessRule(new System.Security.AccessControl.FileSystemAccessRule(
                new System.Security.Principal.SecurityIdentifier(sid, null),
                System.Security.AccessControl.FileSystemRights.FullControl,
                System.Security.AccessControl.AccessControlType.Allow));
        }

        file.SetAccessControl(security);
    }
    catch (Exception)
    {
        // 권한 설정에 실패해도 서버는 동작한다.
    }
}

// 인증서 비밀번호는 자료 폴더에 둔다. 그 폴더는 관리자만 접근할 수 있다.
string GetPasswordPath() => Path.Combine(dataPath, "cert-password.txt");

bool TryReadPassword(out string password)
{
    password = string.Empty;

    try
    {
        var path = GetPasswordPath();
        if (!File.Exists(path)) return false;

        password = File.ReadAllText(path).Trim();
        return password.Length > 0;
    }
    catch (Exception)
    {
        return false;
    }
}

string ReadPassword() => TryReadPassword(out var password) ? password : string.Empty;

void SavePassword(string password)
{
    Directory.CreateDirectory(dataPath);
    File.WriteAllText(GetPasswordPath(), password);
}

// ================= 안내 =================

string? CurrentAddress()
{
    var settingsPath = Path.Combine(installPath, "appsettings.json");
    if (!File.Exists(settingsPath)) return null;

    try
    {
        var root = JsonNode.Parse(File.ReadAllText(settingsPath))?.AsObject();
        var endpoints = root?["Kestrel"]?["Endpoints"]?.AsObject();

        var url = endpoints?["Https"]?["Url"]?.GetValue<string>()
                  ?? endpoints?["Http"]?["Url"]?.GetValue<string>();

        if (url is null) return null;

        var address = NetworkSetup.FindLocalAddress();
        var uri = new Uri(url.Replace("0.0.0.0", address ?? "localhost"));

        return $"{uri.Scheme}://{uri.Host}:{uri.Port}";
    }
    catch (Exception)
    {
        return null;
    }
}

/// <summary>최초 설정 정보 파일에서 아이디와 임시 비밀번호를 읽는다.</summary>
(string Id, string? Password) ReadLoginInfo()
{
    var notePath = Path.Combine(dataPath, "최초설정정보.txt");

    if (!File.Exists(notePath)) return ("admin", null);

    try
    {
        string? password = null;
        var id = "admin";

        foreach (var line in File.ReadAllLines(notePath))
        {
            var parts = line.Split(':', 2);
            if (parts.Length != 2) continue;

            var label = parts[0].Trim();
            var value = parts[1].Trim();

            if (label.Contains("아이디")) id = value;
            else if (label.Contains("임시 비밀번호")) password = value;
        }

        return (id, password);
    }
    catch (Exception)
    {
        return ("admin", null);
    }
}

/// <summary>직원 PC 와 똑같이 사내망에 물어보고 이 서버가 답하는지 본다.</summary>
bool CanBeDiscovered()
{
    try
    {
        // 서버가 막 떴을 수 있으므로 몇 번 시도한다.
        for (var attempt = 0; attempt < 3; attempt++)
        {
            var servers = ServerDiscovery.FindAsync(TimeSpan.FromSeconds(2))
                .GetAwaiter().GetResult();

            if (servers.Any(server =>
                    string.Equals(server.MachineName, Environment.MachineName, StringComparison.OrdinalIgnoreCase)))
            {
                return true;
            }
        }
    }
    catch (Exception)
    {
        // 확인하지 못한 것과 못 찾은 것을 같게 다룬다. 안내를 보여 주는 편이 낫다.
    }

    return false;
}

string DescribeStatus(System.ServiceProcess.ServiceControllerStatus? status) => status switch
{
    System.ServiceProcess.ServiceControllerStatus.Running => "실행 중",
    System.ServiceProcess.ServiceControllerStatus.Stopped => "멈춤",
    System.ServiceProcess.ServiceControllerStatus.StartPending => "시작하는 중",
    System.ServiceProcess.ServiceControllerStatus.StopPending => "멈추는 중",
    null => "설치되지 않음",
    _ => status.ToString() ?? "알 수 없음"
};

[DllImport("user32.dll", CharSet = CharSet.Unicode)]
static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);
