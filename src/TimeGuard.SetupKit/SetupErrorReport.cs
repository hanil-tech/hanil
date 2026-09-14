using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>
/// 설치 중 예상하지 못한 문제가 생겼을 때 사람이 읽을 수 있게 알린다.
///
/// 그냥 두면 Windows 가 "작동이 중지되었습니다" 라는 쓸모없는 창만 띄운다.
/// 무엇이 잘못됐는지 화면에 보여 주고, 자세한 내용은 파일로 남겨
/// 그 파일만 보내면 원인을 찾을 수 있게 한다.
/// </summary>
[SupportedOSPlatform("windows")]
public static class SetupErrorReport
{
    private static string _caption = "설치";

    /// <summary>처리되지 않은 오류를 모두 붙잡도록 준비한다. 프로그램 시작 직후에 부른다.</summary>
    public static void Install(string caption)
    {
        _caption = caption;

        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
        {
            if (e.ExceptionObject is Exception ex) Show(ex);
        };

        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            Show(e.Exception);
            e.SetObserved();
        };
    }

    /// <summary>오류 내용을 창으로 보여 주고 기록 파일 위치를 알려 준다.</summary>
    public static void Show(Exception exception)
    {
        var logPath = WriteLog(exception);

        var text = new StringBuilder();
        text.AppendLine("설치 중 문제가 생겼습니다.");
        text.AppendLine();
        text.AppendLine(Describe(exception));
        text.AppendLine();

        if (logPath is not null)
        {
            text.AppendLine("자세한 내용을 아래 파일에 적어 두었습니다.");
            text.AppendLine(logPath);
            text.AppendLine();
            text.AppendLine("이 파일을 보내 주시면 원인을 찾을 수 있습니다.");
        }

        MessageBoxW(IntPtr.Zero, text.ToString(), _caption, MB_OK | MB_ICONERROR);
    }

    /// <summary>사람이 읽을 수 있는 한 줄 설명. 흔한 원인은 따로 풀어서 알려 준다.</summary>
    public static string Describe(Exception exception)
    {
        var inner = exception;
        while (inner.InnerException is not null) inner = inner.InnerException;

        return inner switch
        {
            UnauthorizedAccessException =>
                "권한이 없어 파일을 다루지 못했습니다.\n" +
                "[관리자 권한으로 실행] 으로 다시 시도해 주세요.\n\n" + inner.Message,

            IOException io when io.Message.Contains("being used") || io.Message.Contains("사용 중") =>
                "다른 프로그램이 파일을 쓰고 있습니다.\n" +
                "실행 중인 TimeGuard 를 모두 닫고 다시 시도해 주세요.\n\n" + io.Message,

            DllNotFoundException or BadImageFormatException =>
                "Windows 구성 요소를 불러오지 못했습니다.\n" +
                "64비트 Windows 10 이상에서 실행해 주세요.\n\n" + inner.Message,

            _ => $"{inner.GetType().Name}: {inner.Message}"
        };
    }

    private static string? WriteLog(Exception exception)
    {
        try
        {
            var path = Path.Combine(Path.GetTempPath(),
                $"TimeGuard-설치오류-{DateTime.Now:yyyyMMdd-HHmmss}.txt");

            var text = new StringBuilder();
            text.AppendLine($"시각      : {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            text.AppendLine($"PC 이름   : {Environment.MachineName}");
            text.AppendLine($"사용자    : {Environment.UserName}");
            text.AppendLine($"Windows   : {Environment.OSVersion}");
            text.AppendLine($"64비트    : {Environment.Is64BitOperatingSystem}");
            text.AppendLine($"실행 위치 : {AppContext.BaseDirectory}");
            text.AppendLine();
            text.AppendLine(exception.ToString());

            File.WriteAllText(path, text.ToString(), Encoding.UTF8);
            return path;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private const uint MB_OK = 0x0;
    private const uint MB_ICONERROR = 0x10;

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);
}
