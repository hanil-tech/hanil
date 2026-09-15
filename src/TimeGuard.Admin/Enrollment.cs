using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;

namespace Hanil.TimeGuard.Admin;

/// <summary>
/// 이 PC 를 관리 서버에 붙이거나 떼어 낸다.
/// 설정 파일만 다루므로 서비스가 떠 있지 않아도 동작한다.
/// </summary>
internal static class Enrollment
{
    internal static int Run(CommandLineOptions options) =>
        options.Command switch
        {
            "enroll" => Enroll(options),
            "unenroll" => Unenroll(),
            "discover" => Discover(),
            "unlock-accounts" => AccountRecovery.UnlockAll(),
            _ => 3
        };

    /// <summary>사내망에서 관리 서버를 찾아 보여 준다.</summary>
    private static int Discover()
    {
        ConsoleUi.Info("사내망에서 관리 서버를 찾는 중입니다...");

        var servers = ServerDiscovery.FindAsync().GetAwaiter().GetResult();

        if (servers.Count == 0)
        {
            ConsoleUi.Error("관리 서버를 찾지 못했습니다.");
            Console.WriteLine();
            ConsoleUi.Dim("  · 서버가 켜져 있는지 확인해 주세요.");
            ConsoleUi.Dim("  · 서버와 이 PC 가 같은 사내망에 있어야 합니다.");
            ConsoleUi.Dim("  · 서버 방화벽에서 UDP 8765 가 열려 있어야 합니다.");
            ConsoleUi.Dim("  · 찾지 못해도 --server 로 주소를 직접 적으면 등록할 수 있습니다.");
            return 2;
        }

        Console.WriteLine();
        foreach (var server in servers)
        {
            ConsoleUi.Success($"{server.Url}");
            ConsoleUi.Dim($"    서버 PC: {server.MachineName} · 버전 {server.Version}");
        }

        Console.WriteLine();
        ConsoleUi.Dim("  등록하려면:");
        ConsoleUi.Dim($"    TimeGuard.Admin.exe enroll --server {servers[0].Url} --key <등록키>");

        return 0;
    }

    /// <summary>
    /// 서버 주소를 정한다. 직접 적었으면 그대로 쓰고, 없으면 사내망에서 찾는다.
    ///
    /// 찾은 결과를 그대로 쓰지 않고 확인을 받는 이유는,
    /// 누군가 가짜 서버를 세워 두었을 수 있기 때문이다.
    /// 관리자가 서버 PC 이름을 보고 맞는지 확인한 뒤 진행한다.
    /// </summary>
    private static string? ResolveServerUrl(CommandLineOptions options)
    {
        if (!string.IsNullOrWhiteSpace(options.ServerUrl)) return options.ServerUrl;

        ConsoleUi.Info("서버 주소가 지정되지 않아 사내망에서 찾아봅니다...");

        var servers = ServerDiscovery.FindAsync().GetAwaiter().GetResult();

        if (servers.Count == 0)
        {
            ConsoleUi.Error("관리 서버를 찾지 못했습니다. --server 로 주소를 직접 적어 주세요.");
            return null;
        }

        if (servers.Count == 1)
        {
            var only = servers[0];

            Console.WriteLine();
            ConsoleUi.Success($"찾았습니다: {only.Url}");
            ConsoleUi.Dim($"  서버 PC 이름: {only.MachineName}");
            Console.WriteLine();

            if (options.AssumeYes) return only.Url;

            return ConsoleUi.Confirm("이 서버가 맞습니까?", defaultYes: true) ? only.Url : null;
        }

        Console.WriteLine();
        ConsoleUi.Warn($"관리 서버가 {servers.Count} 대 발견되었습니다. 어느 것이 맞는지 골라 주세요.");
        Console.WriteLine();

        for (var i = 0; i < servers.Count; i++)
            Console.WriteLine($"  {i + 1}. {servers[i].Url}  (서버 PC: {servers[i].MachineName})");

        Console.WriteLine();

        var choice = ConsoleUi.PromptInt("번호", 1, 1, servers.Count);
        return choice is null ? null : servers[choice.Value - 1].Url;
    }

    private static int Enroll(CommandLineOptions options)
    {
        var url = ResolveServerUrl(options);
        if (url is null)
        {
            ConsoleUi.Info("등록을 취소했습니다.");
            return 3;
        }

        var key = options.EnrollmentKey ?? ConsoleUi.Prompt("클라이언트 등록 키");

        if (string.IsNullOrWhiteSpace(key))
        {
            ConsoleUi.Error("등록 키가 필요합니다. 서버의 [설정] 화면에서 확인할 수 있습니다.");
            return 3;
        }

        if (!Uri.TryCreate(url, UriKind.Absolute, out var parsed) ||
            (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps))
        {
            ConsoleUi.Error("서버 주소가 올바르지 않습니다. http:// 또는 https:// 로 시작해야 합니다.");
            return 3;
        }

        var settings = ServerSettings.Load();
        var target = url.TrimEnd('/');

        // 다른 서버로 옮기는 경우 기억해 둔 인증서를 지운다.
        // (먼저 비교해야 한다. 주소를 덮어쓴 뒤에는 늘 같은 값이 되어 버린다.)
        if (!string.Equals(settings.ServerUrl, target, StringComparison.OrdinalIgnoreCase))
            settings.CertificateThumbprint = string.Empty;

        settings.ServerUrl = target;
        settings.StandaloneMode = false;

        using var connection = new ServerConnection(settings);

        ConsoleUi.Info($"서버에 연결하는 중입니다: {settings.ServerUrl}");

        if (!connection.PingAsync().GetAwaiter().GetResult())
        {
            ConsoleUi.Error("서버에 연결하지 못했습니다.");
            ConsoleUi.Dim("  · 서버 주소와 포트가 맞는지 확인해 주세요.");
            ConsoleUi.Dim("  · 서버 PC 의 방화벽에서 해당 포트가 열려 있어야 합니다.");
            return 2;
        }

        var machineName = Environment.MachineName;
        var osUser = Environment.UserName;

        var (ok, message) = connection.EnrollAsync(machineName, osUser, key).GetAwaiter().GetResult();

        if (!ok)
        {
            ConsoleUi.Error(message);
            return 2;
        }

        ConsoleUi.Success(message);
        Console.WriteLine();
        ConsoleUi.Info($"  PC 이름  : {machineName}");
        ConsoleUi.Info($"  서버     : {settings.ServerUrl}");
        ConsoleUi.Info($"  설정 파일: {ServerSettings.DefaultPath}");
        Console.WriteLine();
        ConsoleUi.Warn("서비스를 다시 시작해야 서버 정책을 받아옵니다.");
        ConsoleUi.Dim("  관리자 권한 명령 프롬프트에서:");
        ConsoleUi.Dim("    net stop HanilTimeGuard && net start HanilTimeGuard");

        return 0;
    }

    private static int Unenroll()
    {
        var settings = ServerSettings.Load();

        if (!settings.IsConfigured)
        {
            ConsoleUi.Info("이 PC 는 이미 단독 모드입니다.");
            return 0;
        }

        ConsoleUi.Warn($"관리 서버({settings.ServerUrl}) 연결을 끊습니다.");
        ConsoleUi.Dim("  이후에는 이 PC 에서 직접 시간표를 설정하게 됩니다.");
        Console.WriteLine();

        if (!ConsoleUi.Confirm("계속할까요?"))
        {
            ConsoleUi.Info("취소했습니다.");
            return 0;
        }

        settings.ServerUrl = string.Empty;
        settings.Token = string.Empty;
        settings.EnrollmentKey = string.Empty;
        settings.CertificateThumbprint = string.Empty;

        // 이걸 켜 두지 않으면 서비스가 사내망에서 서버를 다시 찾아 붙는다.
        settings.StandaloneMode = true;
        settings.Save();

        new PolicyCache().Clear();

        ConsoleUi.Success("단독 모드로 돌렸습니다.");
        ConsoleUi.Warn("서비스를 다시 시작해 주세요: net stop HanilTimeGuard && net start HanilTimeGuard");

        return 0;
    }
}
