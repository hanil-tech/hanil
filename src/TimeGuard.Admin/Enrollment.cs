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
            _ => 3
        };

    private static int Enroll(CommandLineOptions options)
    {
        var url = options.ServerUrl ?? ConsoleUi.Prompt("관리 서버 주소 (예: http://192.168.0.10:8080)");
        var key = options.EnrollmentKey ?? ConsoleUi.Prompt("클라이언트 등록 키");

        if (string.IsNullOrWhiteSpace(url) || string.IsNullOrWhiteSpace(key))
        {
            ConsoleUi.Error("서버 주소와 등록 키가 모두 필요합니다.");
            return 3;
        }

        if (!Uri.TryCreate(url, UriKind.Absolute, out var parsed) ||
            (parsed.Scheme != Uri.UriSchemeHttp && parsed.Scheme != Uri.UriSchemeHttps))
        {
            ConsoleUi.Error("서버 주소가 올바르지 않습니다. http:// 또는 https:// 로 시작해야 합니다.");
            return 3;
        }

        var settings = ServerSettings.Load();
        settings.ServerUrl = url.TrimEnd('/');

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
        settings.Save();

        new PolicyCache().Clear();

        ConsoleUi.Success("단독 모드로 돌렸습니다.");
        ConsoleUi.Warn("서비스를 다시 시작해 주세요: net stop HanilTimeGuard && net start HanilTimeGuard");

        return 0;
    }
}
