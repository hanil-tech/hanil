namespace Hanil.TimeGuard.Admin;

internal sealed class CommandLineOptions
{
    internal string? Command { get; set; }
    internal string? Password { get; set; }
    internal string? NewPassword { get; set; }
    internal int? Minutes { get; set; }
    internal DayOfWeek[]? Day { get; set; }
    internal string? Windows { get; set; }
    internal bool ShowHelp { get; set; }
}

internal static class CommandLine
{
    private static readonly DayOfWeek[] Weekdays =
    {
        DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday
    };

    private static readonly DayOfWeek[] Weekend = { DayOfWeek.Saturday, DayOfWeek.Sunday };

    private static readonly DayOfWeek[] AllDays = Enum.GetValues<DayOfWeek>();

    internal static CommandLineOptions Parse(string[] args)
    {
        var options = new CommandLineOptions();
        var positional = new List<string>();

        for (var i = 0; i < args.Length; i++)
        {
            var arg = args[i];

            switch (arg)
            {
                case "--help" or "-h" or "/?" or "help":
                    options.ShowHelp = true;
                    break;

                case "--password" or "-p" when i + 1 < args.Length:
                    options.Password = args[++i];
                    break;

                case "--new-password" when i + 1 < args.Length:
                    options.NewPassword = args[++i];
                    break;

                default:
                    positional.Add(arg);
                    break;
            }
        }

        if (positional.Count == 0) return options;

        options.Command = positional[0].ToLowerInvariant();

        if (options.Command == "set-window")
        {
            if (positional.Count >= 2) options.Day = ParseDays(positional[1]);
            if (positional.Count >= 3) options.Windows = positional[2];
        }
        else if (positional.Count >= 2 && int.TryParse(positional[1], out var minutes))
        {
            options.Minutes = minutes;
        }

        return options;
    }

    private static DayOfWeek[]? ParseDays(string text) => text.Trim().ToLowerInvariant() switch
    {
        "월" or "월요일" or "mon" or "monday" => new[] { DayOfWeek.Monday },
        "화" or "화요일" or "tue" or "tuesday" => new[] { DayOfWeek.Tuesday },
        "수" or "수요일" or "wed" or "wednesday" => new[] { DayOfWeek.Wednesday },
        "목" or "목요일" or "thu" or "thursday" => new[] { DayOfWeek.Thursday },
        "금" or "금요일" or "fri" or "friday" => new[] { DayOfWeek.Friday },
        "토" or "토요일" or "sat" or "saturday" => new[] { DayOfWeek.Saturday },
        "일" or "일요일" or "sun" or "sunday" => new[] { DayOfWeek.Sunday },
        "평일" or "weekday" or "weekdays" => Weekdays,
        "주말" or "weekend" => Weekend,
        "매일" or "전체" or "all" or "daily" => AllDays,
        _ => null
    };

    internal static void PrintHelp()
    {
        Console.WriteLine("""
            한일 TimeGuard 관리자 도구

            사용법:
              TimeGuard.Admin.exe                          대화형 메뉴를 엽니다
              TimeGuard.Admin.exe status                   현재 상태를 출력합니다
              TimeGuard.Admin.exe enable                   감시를 켭니다
              TimeGuard.Admin.exe disable                  감시를 끕니다
              TimeGuard.Admin.exe extend <분>              지금부터 지정한 분만큼 연장합니다 (0 이면 취소)
              TimeGuard.Admin.exe suspend <분>             지정한 분 동안 감시를 멈춥니다 (0 이면 해제)
              TimeGuard.Admin.exe set-window <요일> <시간대>  허용 시간대를 지정합니다
              TimeGuard.Admin.exe log [줄수]               기록을 출력합니다
              TimeGuard.Admin.exe set-password             관리자 비밀번호를 변경합니다

            공통 옵션:
              -p, --password <비밀번호>      비밀번호를 미리 넘깁니다(자동화용)
                  --new-password <비밀번호>  set-password 에서 쓸 새 비밀번호
              -h, --help                     이 도움말

            요일 표기:
              월 화 수 목 금 토 일 / 평일 / 주말 / 매일

            시간대 표기:
              09:00-18:00              하루 한 구간
              09:00-12:00,13:00-18:00  하루 두 구간
              22:00-06:00              자정을 넘기는 야간 구간
              없음                     그 요일은 사용 불가
              종일                     24시간 허용

            예시:
              TimeGuard.Admin.exe set-window 평일 08:30-18:00 -p 관리자비번
              TimeGuard.Admin.exe set-window 주말 없음 -p 관리자비번
              TimeGuard.Admin.exe extend 30 -p 관리자비번
            """);
    }
}
