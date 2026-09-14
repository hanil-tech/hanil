using System.Runtime.Versioning;
using System.Text;
using Hanil.TimeGuard.Admin;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Schedule;

[assembly: SupportedOSPlatform("windows")]

// 대화형 메뉴가 기본이고, 자동화를 위해 명령줄 인자도 받는다.

try
{
    Console.OutputEncoding = Encoding.UTF8;
    Console.InputEncoding = Encoding.UTF8;
}
catch
{
    // 콘솔 인코딩을 바꿀 수 없는 환경에서는 그대로 진행한다.
}

var options = CommandLine.Parse(args);

if (options.ShowHelp)
{
    CommandLine.PrintHelp();
    return 0;
}

// 서버 등록은 서비스와 무관하게 설정 파일만 다루므로 먼저 처리한다.
if (options.Command is "enroll" or "unenroll" or "discover" or "unlock-accounts")
    return Enrollment.Run(options);

using var session = new AdminSession();

if (!session.ServiceAvailable(out var connectionError))
{
    ConsoleUi.Error("TimeGuard 서비스에 연결할 수 없습니다.");
    if (!string.IsNullOrEmpty(connectionError)) ConsoleUi.Dim("  " + connectionError);
    ConsoleUi.Dim("  서비스가 실행 중인지 확인해 주세요:  sc query HanilTimeGuard");
    return 2;
}

session.UsePassword(options.Password);

if (options.Command is null)
{
    new MenuUi(session).Run();
    return 0;
}

return RunCommand(session, options);

static int RunCommand(AdminSession session, CommandLineOptions options)
{
    switch (options.Command)
    {
        case "status":
        {
            var status = session.GetStatus();
            if (status is null)
            {
                ConsoleUi.Error("상태를 가져오지 못했습니다.");
                return 2;
            }

            Console.WriteLine($"판정      : {MenuUi.DescribeState(status.State)}");
            Console.WriteLine($"감시      : {(status.Enabled ? "켜짐" : "꺼짐")}");
            Console.WriteLine($"근거      : {status.Reason}");
            Console.WriteLine($"조치      : {MenuUi.DescribeAction(status.Action)}");

            if (status.ServerMode)
            {
                Console.WriteLine($"관리 서버 : {status.ServerUrl}");
                Console.WriteLine($"서버 연결 : {(status.ServerReachable ? "정상" : "끊김 (마지막 시간표 적용 중)")}");
            }
            else
            {
                Console.WriteLine("관리 서버 : 사용 안 함 (단독 모드)");
            }

            if (status.RemainingSeconds is { } seconds)
                Console.WriteLine($"남은 시간 : {MenuUi.FormatDuration(TimeSpan.FromSeconds(seconds))}");
            if (status.NextAllowedStart is { } next)
                Console.WriteLine($"다음 사용 : {next:yyyy-MM-dd HH:mm}");

            return status.State == GuardState.Blocked ? 1 : 0;
        }

        case "extend":
        {
            if (options.Minutes is not { } minutes)
            {
                ConsoleUi.Error("연장할 분 수를 지정해 주세요. 예: TimeGuard.Admin.exe extend 30");
                return 3;
            }

            return Report(session.Send(IpcCommands.Extend,
                IpcJson.Serialize(new ExtendRequest { Minutes = minutes })),
                minutes == 0 ? "연장을 취소했습니다." : $"{minutes}분 연장했습니다.");
        }

        case "suspend":
        {
            if (options.Minutes is not { } minutes)
            {
                ConsoleUi.Error("중지할 분 수를 지정해 주세요. 예: TimeGuard.Admin.exe suspend 60");
                return 3;
            }

            return Report(session.Send(IpcCommands.Suspend,
                IpcJson.Serialize(new SuspendRequest { Minutes = minutes })),
                minutes == 0 ? "일시 중지를 해제했습니다." : $"{minutes}분 동안 일시 중지했습니다.");
        }

        case "enable":
            return Report(session.Send(IpcCommands.SetEnabled,
                IpcJson.Serialize(new SetEnabledRequest { Enabled = true })), "감시를 켰습니다.");

        case "disable":
            return Report(session.Send(IpcCommands.SetEnabled,
                IpcJson.Serialize(new SetEnabledRequest { Enabled = false })), "감시를 껐습니다.");

        case "log":
        {
            var response = session.Send(IpcCommands.GetLog,
                IpcJson.Serialize(new GetLogRequest { Lines = options.Minutes ?? 30 }));

            if (!response.Ok)
            {
                ConsoleUi.Error(response.Error ?? "기록을 가져오지 못했습니다.");
                return 2;
            }

            foreach (var line in IpcJson.Deserialize<List<string>>(response.Payload) ?? new List<string>())
                Console.WriteLine(line);

            return 0;
        }

        case "set-password":
        {
            var password = options.NewPassword ?? ConsoleUi.PromptPassword("새 비밀번호");
            return Report(session.Send(IpcCommands.SetPassword,
                IpcJson.Serialize(new SetPasswordRequest { NewPassword = password })), "비밀번호를 변경했습니다.");
        }

        case "set-window":
        {
            if (options.Day is not { } day || options.Windows is null)
            {
                ConsoleUi.Error("사용법: TimeGuard.Admin.exe set-window <요일> <시간대>");
                ConsoleUi.Dim("  예: TimeGuard.Admin.exe set-window 월 09:00-18:00");
                ConsoleUi.Dim("  예: TimeGuard.Admin.exe set-window 평일 09:00-12:00,13:00-18:00");
                return 3;
            }

            if (!MenuUi.TryParseWindows(options.Windows, out var windows, out var parseError))
            {
                ConsoleUi.Error(parseError);
                return 3;
            }

            var config = session.GetConfig();
            if (config is null) return 2;

            foreach (var target in day)
                config.Schedule.SetDay(target, windows.Select(w => new Hanil.TimeGuard.Core.Config.TimeWindow(w.Start, w.End)));

            return session.SaveConfig(config) ? 0 : 2;
        }

        default:
            ConsoleUi.Error($"알 수 없는 명령입니다: {options.Command}");
            CommandLine.PrintHelp();
            return 3;
    }
}

static int Report(IpcResponse response, string successMessage)
{
    if (response.Ok)
    {
        ConsoleUi.Success(successMessage);
        return 0;
    }

    ConsoleUi.Error(response.Error ?? "요청을 처리하지 못했습니다.");
    return 2;
}
