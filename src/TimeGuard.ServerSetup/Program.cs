using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using System.Text.Json.Nodes;
using Hanil.TimeGuard.SetupKit;

[assembly: SupportedOSPlatform("windows")]

// 관리 서버용 설치 프로그램.
// 사무실 PC 한 대에서 더블클릭하면 서버가 준비된다.

const string ServiceName = "HanilTimeGuardServer";
const string DisplayName = "한일 TimeGuard 관리 서버";
const string FirewallRuleName = "한일 TimeGuard 관리 서버";
const string DiscoveryRuleName = "한일 TimeGuard 서버 찾기";
const int DefaultHttpsPort = 8443;
const int DefaultHttpPort = 8080;

var installPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "HanilTimeGuardServer");

var dataPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "HanilTimeGuardServer");

var sourcePath = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
var selfFileName = Path.GetFileName(Environment.ProcessPath ?? "TimeGuard서버-설치.exe");

SetupConsole.Prepare("한일 TimeGuard 관리 서버 설치");

if (!SetupConsole.IsElevated())
{
    SetupConsole.Error("관리자 권한이 필요합니다.");
    SetupConsole.Dim("이 파일을 마우스 오른쪽 클릭 후 [관리자 권한으로 실행] 을 선택해 주세요.");
    SetupConsole.WaitForKey();
    return 1;
}

return ShowMenu();

// ================= 메뉴 =================

int ShowMenu()
{
    while (true)
    {
        Console.Clear();
        SetupConsole.Banner("한일 TimeGuard 관리 서버", "사무실 PC 한 대에 설치합니다");

        var installed = WindowsServiceSetup.Exists(ServiceName);

        if (installed)
        {
            var status = WindowsServiceSetup.GetStatus(ServiceName);
            SetupConsole.Ok($"이미 설치되어 있습니다. (서비스 상태: {DescribeStatus(status)})");
            ShowAddress();
        }
        else
        {
            SetupConsole.Info("아직 설치되지 않았습니다.");
            SetupConsole.Blank();
            SetupConsole.Dim("이 PC 는 업무 시간 동안 켜 두어야 합니다.");
            SetupConsole.Dim("(꺼져 있어도 직원 PC 의 제한은 그대로 유지됩니다)");
        }

        var choice = installed
            ? SetupConsole.Choose("다시 설치 (프로그램 갱신)", "접속 주소와 로그인 정보 보기", "제거")
            : SetupConsole.Choose("설치", "제거");

        switch (choice)
        {
            case 0:
                return 0;

            case 1:
                Install();
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;

            case 2:
                if (installed) ShowLoginInfo();
                else Uninstall();
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;

            case 3:
                Uninstall();
                SetupConsole.WaitForKey("메뉴로 돌아가려면 아무 키나 누르세요.");
                break;
        }
    }
}

// ================= 설치 =================

int Install()
{
    SetupConsole.Blank();
    SetupConsole.Banner("설치를 시작합니다", "잠시만 기다려 주세요");

    if (!File.Exists(Path.Combine(sourcePath, "TimeGuard.Server.exe")))
    {
        SetupConsole.Error("설치 파일을 찾을 수 없습니다.");
        SetupConsole.Dim($"이 프로그램이 있는 폴더: {sourcePath}");
        SetupConsole.Dim("압축을 푼 폴더 안에서 실행해 주세요.");
        return 1;
    }

    // --- 포트 고르기 ---
    SetupConsole.Blank();
    SetupConsole.Info("통신을 암호화하면 사내망에서 비밀번호를 가로챌 수 없습니다.");
    var useHttps = SetupConsole.Confirm("통신을 암호화할까요? (권장)", defaultYes: true);

    var defaultPort = useHttps ? DefaultHttpsPort : DefaultHttpPort;
    var portText = SetupConsole.Prompt("접속 포트", defaultPort.ToString());

    if (!int.TryParse(portText, out var port) || port < 1 || port > 65535)
    {
        SetupConsole.Warn($"포트를 알아볼 수 없어 기본값 {defaultPort} 를 씁니다.");
        port = defaultPort;
    }

    SetupConsole.Blank();

    // --- 기존 서버 정리 ---
    SetupConsole.Step("실행 중인 서버를 정리합니다");

    if (WindowsServiceSetup.Exists(ServiceName))
    {
        if (!WindowsServiceSetup.Stop(ServiceName, out var stopError))
            SetupConsole.Warn($"서버를 멈추지 못했습니다: {stopError}");
    }

    SetupConsole.Ok("정리했습니다.");

    // --- 파일 복사 ---
    SetupConsole.Step($"프로그램을 설치합니다: {installPath}");

    if (!FileSetup.Copy(sourcePath, installPath, selfFileName, out var copyError))
    {
        SetupConsole.Error($"파일을 복사하지 못했습니다: {copyError}");
        return 1;
    }

    SetupConsole.Ok("복사를 마쳤습니다.");

    // --- 자료 폴더 ---
    // 데이터베이스에 관리자 비밀번호와 장비 토큰이 들어 있으므로 일반 사용자는 접근할 수 없게 한다.
    SetupConsole.Step("자료 폴더 권한을 설정합니다");

    if (FileSetup.PrepareDataFolder(dataPath, allowUsersRead: false, out var dataError))
        SetupConsole.Ok("관리자만 접근할 수 있도록 설정했습니다.");
    else
        SetupConsole.Warn($"폴더 권한을 설정하지 못했습니다: {dataError}");

    // --- 암호화 설정 ---
    var scheme = "http";

    if (useHttps)
    {
        SetupConsole.Step("통신 암호화를 준비합니다");

        if (ConfigureHttps(port, out var certError))
        {
            scheme = "https";
            SetupConsole.Ok("인증서를 만들고 암호화를 켰습니다.");
        }
        else
        {
            SetupConsole.Warn($"암호화를 켜지 못했습니다: {certError}");
            SetupConsole.Warn("암호화 없이 설치를 계속합니다.");
            ConfigureHttp(port);
        }
    }
    else
    {
        SetupConsole.Step($"접속 포트를 설정합니다: {port}");
        ConfigureHttp(port);
        SetupConsole.Ok("설정했습니다.");
    }

    // --- 서비스 등록 ---
    SetupConsole.Step("서비스를 등록합니다");

    var binaryPath = Path.Combine(installPath, "TimeGuard.Server.exe");

    if (!WindowsServiceSetup.Register(ServiceName, DisplayName,
            "직원 PC 의 사용 시간표를 관리하고 연장 요청을 받습니다.", binaryPath, out var registerError))
    {
        SetupConsole.Error($"서비스를 등록하지 못했습니다: {registerError}");
        return 1;
    }

    SetupConsole.Ok("등록했습니다.");

    // --- 방화벽 ---
    SetupConsole.Step("사내망에서 접속할 수 있게 방화벽을 엽니다");

    if (NetworkSetup.OpenPort($"{FirewallRuleName} ({port})", port, "TCP", out var firewallError))
        SetupConsole.Ok($"포트 {port} 을(를) 열었습니다. (사내망에서만)");
    else
        SetupConsole.Warn($"방화벽을 열지 못했습니다: {firewallError}");

    // 직원 PC 가 이 서버를 찾을 수 있게 하는 통로.
    if (NetworkSetup.OpenPort(DiscoveryRuleName, 8765, "UDP", out var discoveryError))
        SetupConsole.Ok("직원 PC 가 이 서버를 찾을 수 있게 했습니다.");
    else
        SetupConsole.Warn($"서버 찾기 통로를 열지 못했습니다: {discoveryError}");

    // --- 시작 ---
    SetupConsole.Step("서버를 시작합니다");

    if (!WindowsServiceSetup.Start(ServiceName, out var startError))
    {
        SetupConsole.Error($"서버를 시작하지 못했습니다: {startError}");
        SetupConsole.Dim("이벤트 뷰어의 응용 프로그램 로그를 확인해 주세요.");
        return 1;
    }

    // 최초 설정 정보가 만들어질 때까지 잠시 기다린다.
    Thread.Sleep(4000);
    SetupConsole.Ok("실행 중입니다.");

    // --- 안내 ---
    SetupConsole.Blank();
    SetupConsole.Banner("설치가 끝났습니다", "이제 브라우저로 접속해 설정하세요");

    var address = NetworkSetup.FindLocalAddress();

    Console.WriteLine("  관리 화면 주소");
    Console.WriteLine($"    이 PC 에서   : {scheme}://localhost:{port}");
    if (address is not null)
        Console.WriteLine($"    다른 PC 에서 : {scheme}://{address}:{port}");

    SetupConsole.Blank();
    ShowLoginInfo();

    SetupConsole.Blank();
    Console.WriteLine("  다음 순서");
    Console.WriteLine("    1. 위 주소로 접속해 admin 으로 로그인합니다");
    Console.WriteLine("    2. [설정] 에서 비밀번호를 바꿉니다");
    Console.WriteLine("    3. [기본 시간표] 에서 허용 시간대를 정합니다");
    Console.WriteLine("    4. 직원 PC 에서 설치 프로그램을 실행합니다");
    Console.WriteLine("    5. [새 PC 승인] 에 나타나면 [승인] 을 누릅니다");

    if (scheme == "https")
    {
        SetupConsole.Blank();
        SetupConsole.Dim("  다른 PC 에서 인증서 경고가 뜨면, 아래 파일을 그 PC 로 복사해");
        SetupConsole.Dim("  두 번 클릭 → [인증서 설치] → [로컬 컴퓨터]");
        SetupConsole.Dim("  → [신뢰할 수 있는 루트 인증 기관] 을 선택하십시오.");
        SetupConsole.Dim($"    {Path.Combine(installPath, "서버인증서.cer")}");
        SetupConsole.Dim("  (경고를 무시하고 진행해도 통신은 암호화됩니다.)");
    }

    return 0;
}

// ================= 제거 =================

int Uninstall()
{
    SetupConsole.Blank();
    SetupConsole.Banner("제거", "이 PC 에서 관리 서버를 지웁니다");

    SetupConsole.Warn("서버를 지워도 직원 PC 의 제한은 그대로 유지됩니다.");
    SetupConsole.Dim("직원 PC 의 제한을 풀려면 각 PC 에서 설치 프로그램을 실행해 제거하십시오.");
    SetupConsole.Blank();

    if (!SetupConsole.Confirm("정말 제거할까요?", defaultYes: false))
    {
        SetupConsole.Info("취소했습니다.");
        return 0;
    }

    SetupConsole.Blank();

    SetupConsole.Step("서비스를 지웁니다");

    if (WindowsServiceSetup.Delete(ServiceName, out var deleteError))
        SetupConsole.Ok("지웠습니다.");
    else
        SetupConsole.Warn($"서비스를 지우지 못했습니다: {deleteError}");

    SetupConsole.Step("방화벽 규칙을 지웁니다");

    foreach (var port in new[] { DefaultHttpsPort, DefaultHttpPort })
        NetworkSetup.ClosePort($"{FirewallRuleName} ({port})");

    NetworkSetup.ClosePort(DiscoveryRuleName);
    SetupConsole.Ok("지웠습니다.");

    Thread.Sleep(2000);

    SetupConsole.Step("프로그램 파일을 지웁니다");

    if (FileSetup.RemoveFolder(installPath, out var removeError))
        SetupConsole.Ok("지웠습니다.");
    else
        SetupConsole.Warn($"일부 파일을 지우지 못했습니다: {removeError}");

    SetupConsole.Blank();

    if (SetupConsole.Confirm("설정과 기록(데이터베이스)을 남겨 둘까요?", defaultYes: true))
    {
        SetupConsole.Info($"자료는 그대로 두었습니다: {dataPath}");
    }
    else
    {
        SetupConsole.Step("자료를 지웁니다");

        if (FileSetup.RemoveFolder(dataPath, out var dataRemoveError))
            SetupConsole.Ok("지웠습니다.");
        else
            SetupConsole.Warn($"지우지 못했습니다: {dataRemoveError}");
    }

    SetupConsole.Blank();
    SetupConsole.Banner("제거가 끝났습니다", "");

    return 0;
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
        var publicPath = Path.Combine(installPath, "서버인증서.cer");

        // 이미 쓰던 인증서가 있으면 그대로 쓴다.
        // 새로 만들면 직원 PC 들이 기억해 둔 것과 달라져 모두 다시 등록해야 한다.
        var reuse = File.Exists(certificatePath) && TryReadPassword(out var existingPassword);

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

void ShowAddress()
{
    var settingsPath = Path.Combine(installPath, "appsettings.json");
    if (!File.Exists(settingsPath)) return;

    try
    {
        var root = JsonNode.Parse(File.ReadAllText(settingsPath))?.AsObject();
        var endpoints = root?["Kestrel"]?["Endpoints"]?.AsObject();

        var url = endpoints?["Https"]?["Url"]?.GetValue<string>()
                  ?? endpoints?["Http"]?["Url"]?.GetValue<string>();

        if (url is null) return;

        var address = NetworkSetup.FindLocalAddress();
        var uri = new Uri(url.Replace("0.0.0.0", address ?? "localhost"));

        SetupConsole.Info($"관리 화면: {uri.Scheme}://{uri.Host}:{uri.Port}");
    }
    catch (Exception)
    {
        // 주소를 못 읽어도 메뉴는 정상 동작한다.
    }
}

void ShowLoginInfo()
{
    var notePath = Path.Combine(dataPath, "최초설정정보.txt");

    if (!File.Exists(notePath))
    {
        SetupConsole.Info("  최초 로그인 정보가 없습니다. 이미 비밀번호를 바꾸셨다면 정상입니다.");
        return;
    }

    Console.WriteLine("  최초 로그인 정보");

    foreach (var line in File.ReadAllLines(notePath))
        Console.WriteLine($"    {line}");

    SetupConsole.Blank();
    SetupConsole.Warn($"로그인 후 비밀번호를 바꾸고 이 파일을 지우십시오: {notePath}");
}

string DescribeStatus(System.ServiceProcess.ServiceControllerStatus? status) => status switch
{
    System.ServiceProcess.ServiceControllerStatus.Running => "실행 중",
    System.ServiceProcess.ServiceControllerStatus.Stopped => "멈춤",
    null => "설치되지 않음",
    _ => status.ToString() ?? "알 수 없음"
};
