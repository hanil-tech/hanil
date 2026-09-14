using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Schedule;

namespace Hanil.TimeGuard.Admin;

/// <summary>대화형 관리자 메뉴.</summary>
internal sealed class MenuUi
{
    private static readonly DayOfWeek[] WeekOrder =
    {
        DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday,
        DayOfWeek.Friday, DayOfWeek.Saturday, DayOfWeek.Sunday
    };

    private static readonly DayOfWeek[] Weekdays =
    {
        DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday, DayOfWeek.Friday
    };

    private readonly AdminSession _session;

    internal MenuUi(AdminSession session) => _session = session;

    internal void Run()
    {
        while (true)
        {
            Console.Clear();
            ConsoleUi.Title("한일 TimeGuard — 관리자 설정");
            PrintStatusLine();

            var serverManaged = PrintServerLine();

            Console.WriteLine();
            Console.WriteLine("  1. 현재 상태 자세히 보기");
            Console.WriteLine("  2. 허용 시간대 설정");
            Console.WriteLine("  3. 감시 켜기 / 끄기");
            Console.WriteLine("  4. 시간 초과 시 조치 변경");
            Console.WriteLine("  5. 경고 방식 설정");
            Console.WriteLine("  6. 임시 연장 부여");
            Console.WriteLine("  7. 일시 중지 / 해제");
            Console.WriteLine("  8. 휴일 관리");
            Console.WriteLine("  9. 제한 제외 계정 관리");
            Console.WriteLine(" 10. 관리자 비밀번호 변경");
            Console.WriteLine(" 11. 기록 보기");
            Console.WriteLine("  0. 종료");
            Console.WriteLine();

            var choice = ConsoleUi.Prompt("선택");

            // 서버가 관리하는 PC 에서는 설정 변경 메뉴가 동작하지 않는다. 미리 알려 준다.
            if (serverManaged && choice is "2" or "3" or "4" or "5" or "6" or "7" or "8" or "9")
            {
                ConsoleUi.Warn("이 PC 는 관리 서버가 설정을 관리합니다.");
                ConsoleUi.Dim("  시간표 변경과 연장은 서버의 웹 화면에서 해 주세요.");
                ConsoleUi.Pause();
                continue;
            }

            switch (choice)
            {
                case "1": ShowStatus(); break;
                case "2": EditSchedule(); break;
                case "3": ToggleEnabled(); break;
                case "4": EditAction(); break;
                case "5": EditWarnings(); break;
                case "6": GrantExtension(); break;
                case "7": ToggleSuspend(); break;
                case "8": EditHolidays(); break;
                case "9": EditExemptUsers(); break;
                case "10": ChangePassword(); break;
                case "11": ShowLog(); break;
                case "0": case "q": case "Q": return;
                default:
                    ConsoleUi.Warn("메뉴 번호를 입력해 주세요.");
                    ConsoleUi.Pause();
                    break;
            }
        }
    }

    // ---- 상태 ----

    private void PrintStatusLine()
    {
        var status = _session.GetStatus();

        if (status is null)
        {
            ConsoleUi.Error("서비스에 연결할 수 없습니다. TimeGuard 서비스가 실행 중인지 확인해 주세요.");
            return;
        }

        switch (status.State)
        {
            case GuardState.Disabled:
                ConsoleUi.Warn(status.Enabled
                    ? $"일시 중지 중 — {status.Reason}"
                    : "감시 꺼짐 — 현재 아무도 제한받지 않습니다.");
                break;

            case GuardState.Allowed:
                var remaining = status.RemainingSeconds is { } seconds
                    ? FormatDuration(TimeSpan.FromSeconds(seconds))
                    : "-";
                ConsoleUi.Success($"사용 가능 — {remaining} 남음 (종료 {status.WindowEnd:HH:mm})");
                break;

            case GuardState.Blocked:
                ConsoleUi.Error($"차단 상태 — {status.Reason}");
                break;
        }
    }

    /// <summary>관리 서버를 쓰는 PC 인지 알려 주고, 그 여부를 돌려준다.</summary>
    private bool PrintServerLine()
    {
        var status = _session.GetStatus();
        if (status is null || !status.ServerMode) return false;

        if (status.ServerReachable)
            ConsoleUi.Info($"관리 서버: {status.ServerUrl} (연결됨) — 설정은 서버에서 변경합니다.");
        else
            ConsoleUi.Warn($"관리 서버: {status.ServerUrl} (연결 끊김) — 마지막으로 받은 시간표가 적용 중입니다.");

        return true;
    }

    private void ShowStatus()
    {
        ConsoleUi.Title("현재 상태");

        var status = _session.GetStatus();
        if (status is null)
        {
            ConsoleUi.Error("서비스에 연결할 수 없습니다.");
            ConsoleUi.Pause();
            return;
        }

        Console.WriteLine($"  서비스 시각      : {status.ServerTime:yyyy-MM-dd HH:mm:ss}");
        Console.WriteLine($"  감시 사용        : {(status.Enabled ? "켜짐" : "꺼짐")}");
        Console.WriteLine($"  현재 판정        : {DescribeState(status.State)}");
        Console.WriteLine($"  판정 근거        : {status.Reason}");
        Console.WriteLine($"  시간 초과 시 조치: {DescribeAction(status.Action)}");

        if (status.ServerMode)
        {
            Console.WriteLine($"  관리 서버        : {status.ServerUrl}");
            Console.WriteLine($"  서버 연결        : {(status.ServerReachable ? "정상" : "끊김 (마지막 시간표 적용 중)")}");
        }
        else
        {
            Console.WriteLine("  관리 서버        : 사용 안 함 (단독 모드)");
        }

        if (status.RemainingSeconds is { } seconds)
            Console.WriteLine($"  남은 시간        : {FormatDuration(TimeSpan.FromSeconds(seconds))}");
        if (status.WindowEnd is { } end)
            Console.WriteLine($"  사용 종료 시각   : {end:yyyy-MM-dd HH:mm}");
        if (status.NextAllowedStart is { } next)
            Console.WriteLine($"  다음 사용 가능   : {next:yyyy-MM-dd HH:mm}");
        if (status.SuspendedUntil is { } suspended)
            Console.WriteLine($"  일시 중지        : {suspended:yyyy-MM-dd HH:mm} 까지");
        if (status.ExtensionUntil is { } extension)
            Console.WriteLine($"  연장             : {extension:yyyy-MM-dd HH:mm} 까지");
        if (!string.IsNullOrEmpty(status.Warning))
            ConsoleUi.Warn($"  경고             : {status.Warning}");

        var config = _session.GetConfig();
        if (config is not null)
        {
            Console.WriteLine($"  원격 접속 차단   : {(config.BlockRemoteAccess ? "사용" : "사용 안 함")}");
            Console.WriteLine($"  원격 제어 차단   : {(config.BlockRemoteTools ? "사용" : "사용 안 함")}");
            Console.WriteLine();
            PrintSchedule(config);
        }

        ConsoleUi.Pause();
    }

    // ---- 허용 시간대 ----

    private static void PrintSchedule(GuardConfig config)
    {
        Console.WriteLine("  허용 시간대");
        foreach (var day in WeekOrder)
        {
            var windows = config.Schedule.ForDay(day);
            var text = windows.Count == 0
                ? "사용 불가"
                : string.Join(", ", windows.Select(w => w.ToString()));

            Console.WriteLine($"    {KoreanDay(day)}  {text}");
        }

        if (config.Holidays.Count > 0)
        {
            var policy = config.HolidayPolicy == HolidayPolicy.Blocked ? "사용 불가" : "제한 없음";
            Console.WriteLine($"  지정 휴일({policy}): {string.Join(", ", config.Holidays)}");
        }

        if (config.ExemptUsers.Count > 0)
            Console.WriteLine($"  제외 계정: {string.Join(", ", config.ExemptUsers)}");
    }

    private void EditSchedule()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        while (true)
        {
            Console.Clear();
            ConsoleUi.Title("허용 시간대 설정");
            PrintSchedule(config);

            Console.WriteLine();
            Console.WriteLine("  1. 요일 하나씩 지정");
            Console.WriteLine("  2. 평일(월~금) 한 번에 지정");
            Console.WriteLine("  3. 모든 요일 같게 지정");
            Console.WriteLine("  4. 주말 사용 금지로 설정");
            Console.WriteLine("  0. 저장하고 돌아가기");
            Console.WriteLine();
            ConsoleUi.Dim("  입력 예시: 09:00-18:00  /  09:00-12:00,13:00-18:00  /  22:00-06:00(야간)  /  없음");
            Console.WriteLine();

            switch (ConsoleUi.Prompt("선택"))
            {
                case "1": EditSingleDay(config); break;
                case "2": ApplyToDays(config, Weekdays, "평일(월~금)"); break;
                case "3": ApplyToDays(config, WeekOrder, "모든 요일"); break;
                case "4":
                    config.Schedule.ClearDay(DayOfWeek.Saturday);
                    config.Schedule.ClearDay(DayOfWeek.Sunday);
                    ConsoleUi.Success("주말을 사용 불가로 설정했습니다.");
                    break;
                case "0":
                    _session.SaveConfig(config);
                    ConsoleUi.Pause();
                    return;
                default:
                    ConsoleUi.Warn("메뉴 번호를 입력해 주세요.");
                    break;
            }
        }
    }

    private static void EditSingleDay(GuardConfig config)
    {
        Console.WriteLine();
        for (var i = 0; i < WeekOrder.Length; i++)
            Console.WriteLine($"  {i + 1}. {KoreanDay(WeekOrder[i])}");

        var index = ConsoleUi.PromptInt("요일 번호", min: 1, max: WeekOrder.Length);
        if (index is null) return;

        var day = WeekOrder[index.Value - 1];
        ApplyToDays(config, new[] { day }, KoreanDay(day));
    }

    private static void ApplyToDays(GuardConfig config, DayOfWeek[] days, string label)
    {
        var current = config.Schedule.ForDay(days[0]);
        var suggestion = current.Count == 0 ? "없음" : string.Join(",", current.Select(w => w.ToString()));

        var input = ConsoleUi.Prompt($"{label} 허용 시간대", suggestion);

        if (!TryParseWindows(input, out var windows, out var error))
        {
            ConsoleUi.Error(error);
            return;
        }

        foreach (var day in days) config.Schedule.SetDay(day, windows.Select(w => new TimeWindow(w.Start, w.End)));

        ConsoleUi.Success(windows.Count == 0
            ? $"{label}을(를) 사용 불가로 설정했습니다."
            : $"{label}을(를) {string.Join(", ", windows.Select(w => w.ToString()))} 로 설정했습니다.");
    }

    /// <summary>"09:00-12:00,13:00-18:00" 또는 "없음" 을 해석한다.</summary>
    internal static bool TryParseWindows(string input, out List<TimeWindow> windows, out string error)
    {
        windows = new List<TimeWindow>();
        error = string.Empty;

        input = input.Trim();

        if (input.Length == 0 || input is "없음" or "-" or "none" or "금지")
            return true; // 빈 목록 = 사용 불가

        if (input is "종일" or "24시간" or "all")
        {
            windows.Add(new TimeWindow(TimeOnly.MinValue, TimeOnly.MinValue));
            return true;
        }

        foreach (var part in input.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!TimeWindow.TryParse(part, out var window))
            {
                error = $"'{part}' 를 해석하지 못했습니다. 09:00-18:00 형식으로 입력해 주세요.";
                windows.Clear();
                return false;
            }

            windows.Add(window);
        }

        // 겹치는 구간이 있으면 알려 준다(동작은 하지만 의도치 않은 설정일 가능성이 높다).
        var sorted = windows.Where(w => !w.CrossesMidnight).OrderBy(w => w.Start).ToList();
        for (var i = 1; i < sorted.Count; i++)
        {
            if (sorted[i].Start < sorted[i - 1].End)
            {
                error = $"{sorted[i - 1]} 와 {sorted[i]} 구간이 겹칩니다.";
                windows.Clear();
                return false;
            }
        }

        return true;
    }

    // ---- 켜기/끄기, 조치 ----

    private void ToggleEnabled()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        ConsoleUi.Title("감시 켜기 / 끄기");
        Console.WriteLine($"  현재: {(config.Enabled ? "켜짐" : "꺼짐")}");
        Console.WriteLine();

        var turnOn = !config.Enabled;

        if (turnOn)
        {
            ConsoleUi.Warn("감시를 켜면 허용 시간대를 벗어날 때 실제로 조치가 실행됩니다.");
            PrintSchedule(config);
            Console.WriteLine();
            Console.WriteLine($"  시간 초과 시 조치: {DescribeAction(config.Action)}");
            Console.WriteLine();
        }

        if (!ConsoleUi.Confirm(turnOn ? "감시를 켤까요?" : "감시를 끌까요?"))
        {
            ConsoleUi.Info("취소했습니다.");
            ConsoleUi.Pause();
            return;
        }

        var response = _session.Send(IpcCommands.SetEnabled,
            IpcJson.Serialize(new SetEnabledRequest { Enabled = turnOn }));

        if (response.Ok)
            ConsoleUi.Success(turnOn ? "감시를 켰습니다." : "감시를 껐습니다.");
        else
            ConsoleUi.Error(response.Error ?? "변경하지 못했습니다.");

        ConsoleUi.Pause();
    }

    private void EditAction()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        ConsoleUi.Title("시간 초과 시 조치");
        Console.WriteLine($"  현재: {DescribeAction(config.Action)}");
        Console.WriteLine();
        Console.WriteLine("  1. 전원 차단  — 컴퓨터를 끕니다. 가장 확실합니다.");
        Console.WriteLine("  2. 계정 잠금  — 로그오프하고 다시 로그인할 수 없게 합니다.");
        Console.WriteLine("                  직원이 스스로 풀 수 없고, 허용 시간이 되면 자동으로 풀립니다.");
        Console.WriteLine("  3. 로그오프   — 로그아웃만 합니다. 바로 다시 로그인할 수 있습니다.");
        Console.WriteLine("  4. 화면 잠금  — 직원이 자기 비밀번호로 바로 풉니다. 제한 효과가 거의 없습니다.");
        Console.WriteLine("  0. 변경하지 않음");
        Console.WriteLine();

        var choice = ConsoleUi.Prompt("선택");
        GuardAction? action = choice switch
        {
            "1" => GuardAction.Shutdown,
            "2" => GuardAction.AccountLock,
            "3" => GuardAction.LogOff,
            "4" => GuardAction.Lock,
            _ => null
        };

        if (action == GuardAction.AccountLock)
        {
            Console.WriteLine();
            ConsoleUi.Warn("계정 잠금은 직원이 Windows 에 로그인하지 못하게 만듭니다.");
            ConsoleUi.Dim("  · 허용 시간이 되면 서비스가 자동으로 풀어 줍니다.");
            ConsoleUi.Dim("  · 관리자 권한을 가진 계정에는 적용되지 않습니다.");
            ConsoleUi.Dim("  · 문제가 생기면 TimeGuard.Admin.exe unlock-accounts 로 되돌릴 수 있습니다.");
            Console.WriteLine();

            if (!ConsoleUi.Confirm("계정 잠금으로 설정할까요?"))
            {
                ConsoleUi.Info("변경하지 않았습니다.");
                ConsoleUi.Pause();
                return;
            }
        }

        if (action is null)
        {
            ConsoleUi.Info("변경하지 않았습니다.");
            ConsoleUi.Pause();
            return;
        }

        config.Action = action.Value;

        Console.WriteLine();
        ConsoleUi.Dim("  계정을 잠가도 PC 에 다른 계정이 있으면 그 계정으로 원격 접속해 쓸 수 있습니다.");

        config.BlockRemoteAccess = ConsoleUi.Confirm(
            "허용 시간이 아닐 때 Windows 원격 데스크톱 접속도 막을까요?",
            defaultYes: config.BlockRemoteAccess);

        Console.WriteLine();
        ConsoleUi.Dim("  팀뷰어·AnyDesk 같은 프로그램은 서비스로 상주해");
        ConsoleUi.Dim("  로그아웃 상태에서도 접속을 받아 줍니다.");
        ConsoleUi.Dim($"  기본으로 막는 프로그램: {string.Join(", ", RemoteTools.DefaultDisplayNames.Take(6))} 등");

        config.BlockRemoteTools = ConsoleUi.Confirm(
            "원격 제어 프로그램도 막을까요?",
            defaultYes: config.BlockRemoteTools);

        if (config.BlockRemoteTools)
        {
            var extra = ConsoleUi.Prompt("추가로 막을 프로그램 이름(쉼표로 구분, 없으면 Enter)",
                string.Join(", ", config.ExtraRemoteToolNames));

            config.ExtraRemoteToolNames = extra
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(RemoteTools.Normalize)
                .Where(n => n.Length > 0)
                .Distinct()
                .ToList();
        }

        _session.SaveConfig(config);
        ConsoleUi.Pause();
    }

    private void EditWarnings()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        ConsoleUi.Title("경고 방식 설정");

        var warnings = config.Warnings;
        Console.WriteLine($"  현재 경고 단계   : 종료 {string.Join(", ", warnings.OrderedNoticeMinutes)}분 전");
        Console.WriteLine($"  마지막 카운트다운: {warnings.CountdownSeconds}초");
        Console.WriteLine($"  시간 밖 부팅 유예: {warnings.OutsideWindowGraceSeconds}초");
        Console.WriteLine($"  안내 문구        : {warnings.Message}");
        Console.WriteLine();

        var noticeInput = ConsoleUi.Prompt("경고 단계(분, 쉼표로 구분)",
            string.Join(",", warnings.OrderedNoticeMinutes));

        var minutes = new List<int>();
        foreach (var part in noticeInput.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (int.TryParse(part, out var value) && value > 0)
                minutes.Add(value);
            else
            {
                ConsoleUi.Error($"'{part}' 는 분 단위 숫자가 아닙니다. 변경을 취소합니다.");
                ConsoleUi.Pause();
                return;
            }
        }

        if (minutes.Count > 0) warnings.NoticeMinutes = minutes;

        warnings.CountdownSeconds =
            ConsoleUi.PromptInt("마지막 카운트다운(초)", warnings.CountdownSeconds, 0, 600) ?? warnings.CountdownSeconds;

        warnings.OutsideWindowGraceSeconds =
            ConsoleUi.PromptInt("허용 시간 밖에서 켰을 때 유예(초)", warnings.OutsideWindowGraceSeconds, 0, 3600)
            ?? warnings.OutsideWindowGraceSeconds;

        warnings.Message = ConsoleUi.Prompt("안내 문구", warnings.Message);

        _session.SaveConfig(config);
        ConsoleUi.Pause();
    }

    // ---- 연장 / 일시 중지 ----

    private void GrantExtension()
    {
        ConsoleUi.Title("임시 연장 부여");

        var status = _session.GetStatus();
        if (status?.ExtensionUntil is { } current && current > DateTimeOffset.Now)
            Console.WriteLine($"  현재 연장: {current:yyyy-MM-dd HH:mm} 까지");

        Console.WriteLine();
        ConsoleUi.Dim("  지금부터 몇 분 더 쓸 수 있게 할지 입력합니다. 0 을 넣으면 연장을 취소합니다.");

        var minutes = ConsoleUi.PromptInt("연장 시간(분)", 30, 0, 1440);
        if (minutes is null) return;

        var response = _session.Send(IpcCommands.Extend,
            IpcJson.Serialize(new ExtendRequest { Minutes = minutes.Value }));

        if (response.Ok)
        {
            ConsoleUi.Success(minutes.Value == 0
                ? "연장을 취소했습니다."
                : $"{minutes.Value}분 연장했습니다.");
        }
        else
        {
            ConsoleUi.Error(response.Error ?? "연장하지 못했습니다.");
        }

        ConsoleUi.Pause();
    }

    private void ToggleSuspend()
    {
        ConsoleUi.Title("일시 중지 / 해제");

        var status = _session.GetStatus();
        if (status?.SuspendedUntil is { } current && current > DateTimeOffset.Now)
        {
            Console.WriteLine($"  현재 {current:yyyy-MM-dd HH:mm} 까지 일시 중지 중입니다.");
            Console.WriteLine();

            if (ConsoleUi.Confirm("일시 중지를 해제할까요?", defaultYes: true))
            {
                var cancel = _session.Send(IpcCommands.Suspend,
                    IpcJson.Serialize(new SuspendRequest { Minutes = 0 }));

                if (cancel.Ok) ConsoleUi.Success("일시 중지를 해제했습니다.");
                else ConsoleUi.Error(cancel.Error ?? "해제하지 못했습니다.");
            }

            ConsoleUi.Pause();
            return;
        }

        ConsoleUi.Dim("  점검이나 야근 등으로 잠시 제한을 멈출 때 사용합니다.");

        var minutes = ConsoleUi.PromptInt("중지 시간(분)", 60, 0, 10080);
        if (minutes is null || minutes == 0) return;

        var response = _session.Send(IpcCommands.Suspend,
            IpcJson.Serialize(new SuspendRequest { Minutes = minutes.Value }));

        if (response.Ok) ConsoleUi.Success($"{minutes.Value}분 동안 일시 중지했습니다.");
        else ConsoleUi.Error(response.Error ?? "일시 중지하지 못했습니다.");

        ConsoleUi.Pause();
    }

    // ---- 휴일 / 제외 계정 ----

    private void EditHolidays()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        while (true)
        {
            Console.Clear();
            ConsoleUi.Title("휴일 관리");

            Console.WriteLine($"  휴일 처리: {(config.HolidayPolicy == HolidayPolicy.Blocked ? "사용 불가" : "제한 없음")}");
            Console.WriteLine();

            if (config.Holidays.Count == 0)
                ConsoleUi.Dim("  등록된 휴일이 없습니다.");
            else
                foreach (var holiday in config.Holidays) Console.WriteLine($"    {holiday}");

            Console.WriteLine();
            Console.WriteLine("  1. 휴일 추가");
            Console.WriteLine("  2. 휴일 삭제");
            Console.WriteLine("  3. 휴일 처리 방식 바꾸기");
            Console.WriteLine("  0. 저장하고 돌아가기");
            Console.WriteLine();

            switch (ConsoleUi.Prompt("선택"))
            {
                case "1":
                    var add = ConsoleUi.Prompt("추가할 날짜(yyyy-MM-dd)");
                    if (DateOnly.TryParse(add, out var addDate))
                    {
                        config.AddHoliday(addDate);
                        ConsoleUi.Success($"{addDate:yyyy-MM-dd} 을(를) 휴일로 추가했습니다.");
                    }
                    else ConsoleUi.Error("날짜 형식이 올바르지 않습니다.");
                    break;

                case "2":
                    var remove = ConsoleUi.Prompt("삭제할 날짜(yyyy-MM-dd)");
                    if (DateOnly.TryParse(remove, out var removeDate))
                    {
                        config.RemoveHoliday(removeDate);
                        ConsoleUi.Success($"{removeDate:yyyy-MM-dd} 을(를) 삭제했습니다.");
                    }
                    else ConsoleUi.Error("날짜 형식이 올바르지 않습니다.");
                    break;

                case "3":
                    config.HolidayPolicy = config.HolidayPolicy == HolidayPolicy.Blocked
                        ? HolidayPolicy.Unrestricted
                        : HolidayPolicy.Blocked;
                    ConsoleUi.Success($"휴일 처리를 '{(config.HolidayPolicy == HolidayPolicy.Blocked ? "사용 불가" : "제한 없음")}' 로 바꿨습니다.");
                    break;

                case "0":
                    _session.SaveConfig(config);
                    ConsoleUi.Pause();
                    return;

                default:
                    ConsoleUi.Warn("메뉴 번호를 입력해 주세요.");
                    break;
            }
        }
    }

    private void EditExemptUsers()
    {
        var config = _session.GetConfig();
        if (config is null) { ConsoleUi.Pause(); return; }

        while (true)
        {
            Console.Clear();
            ConsoleUi.Title("제한 제외 계정");
            ConsoleUi.Dim("  여기 등록된 Windows 계정으로 로그인하면 시간 제한을 받지 않습니다.");
            Console.WriteLine();

            if (config.ExemptUsers.Count == 0)
                ConsoleUi.Dim("  등록된 계정이 없습니다.");
            else
                foreach (var user in config.ExemptUsers) Console.WriteLine($"    {user}");

            Console.WriteLine();
            Console.WriteLine("  1. 계정 추가");
            Console.WriteLine("  2. 계정 삭제");
            Console.WriteLine("  0. 저장하고 돌아가기");
            Console.WriteLine();

            switch (ConsoleUi.Prompt("선택"))
            {
                case "1":
                    var add = ConsoleUi.Prompt("추가할 계정 이름");
                    if (!string.IsNullOrWhiteSpace(add) && !config.ExemptUsers.Contains(add))
                    {
                        config.ExemptUsers.Add(add);
                        ConsoleUi.Success($"'{add}' 계정을 추가했습니다.");
                    }
                    break;

                case "2":
                    var remove = ConsoleUi.Prompt("삭제할 계정 이름");
                    if (config.ExemptUsers.Remove(remove))
                        ConsoleUi.Success($"'{remove}' 계정을 삭제했습니다.");
                    else
                        ConsoleUi.Warn("목록에 없는 계정입니다.");
                    break;

                case "0":
                    _session.SaveConfig(config);
                    ConsoleUi.Pause();
                    return;

                default:
                    ConsoleUi.Warn("메뉴 번호를 입력해 주세요.");
                    break;
            }
        }
    }

    // ---- 비밀번호 / 기록 ----

    private void ChangePassword()
    {
        ConsoleUi.Title("관리자 비밀번호 변경");
        ConsoleUi.Dim("  8자 이상, 숫자만으로는 설정할 수 없습니다.");
        Console.WriteLine();

        var first = ConsoleUi.PromptPassword("새 비밀번호");
        if (string.IsNullOrEmpty(first))
        {
            ConsoleUi.Info("취소했습니다.");
            ConsoleUi.Pause();
            return;
        }

        var second = ConsoleUi.PromptPassword("새 비밀번호 확인");
        if (first != second)
        {
            ConsoleUi.Error("두 번 입력한 비밀번호가 서로 다릅니다.");
            ConsoleUi.Pause();
            return;
        }

        var response = _session.Send(IpcCommands.SetPassword,
            IpcJson.Serialize(new SetPasswordRequest { NewPassword = first }));

        if (response.Ok)
        {
            ConsoleUi.Success("비밀번호를 변경했습니다.");
            _session.UsePassword(first);
        }
        else
        {
            ConsoleUi.Error(response.Error ?? "비밀번호를 변경하지 못했습니다.");
        }

        ConsoleUi.Pause();
    }

    private void ShowLog()
    {
        ConsoleUi.Title("기록");

        var lines = ConsoleUi.PromptInt("몇 줄을 볼까요?", 30, 1, 500) ?? 30;

        var response = _session.Send(IpcCommands.GetLog, IpcJson.Serialize(new GetLogRequest { Lines = lines }));
        if (!response.Ok)
        {
            ConsoleUi.Error(response.Error ?? "기록을 가져오지 못했습니다.");
            ConsoleUi.Pause();
            return;
        }

        var entries = IpcJson.Deserialize<List<string>>(response.Payload) ?? new List<string>();

        Console.WriteLine();
        if (entries.Count == 0) ConsoleUi.Dim("  기록이 없습니다.");
        else foreach (var entry in entries) Console.WriteLine("  " + entry);

        ConsoleUi.Pause();
    }

    // ---- 표시용 문자열 ----

    internal static string KoreanDay(DayOfWeek day) => day switch
    {
        DayOfWeek.Monday => "월요일",
        DayOfWeek.Tuesday => "화요일",
        DayOfWeek.Wednesday => "수요일",
        DayOfWeek.Thursday => "목요일",
        DayOfWeek.Friday => "금요일",
        DayOfWeek.Saturday => "토요일",
        DayOfWeek.Sunday => "일요일",
        _ => day.ToString()
    };

    internal static string DescribeAction(GuardAction action) => action switch
    {
        GuardAction.Shutdown => "전원 차단",
        GuardAction.AccountLock => "계정 잠금",
        GuardAction.LogOff => "로그오프",
        GuardAction.Lock => "화면 잠금(직원이 풀 수 있음)",
        _ => action.ToString()
    };

    internal static string DescribeState(GuardState state) => state switch
    {
        GuardState.Allowed => "사용 가능",
        GuardState.Blocked => "차단",
        GuardState.Disabled => "제한 없음",
        _ => state.ToString()
    };

    internal static string FormatDuration(TimeSpan duration)
    {
        if (duration < TimeSpan.Zero) duration = TimeSpan.Zero;

        if (duration.TotalHours >= 1)
            return $"{(int)duration.TotalHours}시간 {duration.Minutes}분";
        if (duration.TotalMinutes >= 1)
            return $"{(int)duration.TotalMinutes}분 {duration.Seconds}초";

        return $"{(int)duration.TotalSeconds}초";
    }
}
