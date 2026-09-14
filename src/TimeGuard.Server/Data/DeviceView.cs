using Hanil.TimeGuard.Core.Config;

namespace Hanil.TimeGuard.Server.Data;

/// <summary>화면에 뿌리기 좋게 장비 정보를 정리한 것.</summary>
public sealed class DeviceView
{
    public required Device Device { get; init; }
    public required bool Online { get; init; }
    public int PendingRequests { get; init; }

    public string Id => Device.Id;
    public string Name => string.IsNullOrWhiteSpace(Device.DisplayName) ? Device.MachineName : Device.DisplayName;

    /// <summary>표에 표시할 상태 문구와 색 구분용 이름.</summary>
    public (string Label, string Css) Status
    {
        get
        {
            if (!Online) return ("연결 끊김", "offline");
            if (!Device.Enforced) return ("제한 없음", "disabled");

            if (Device.SuspendedUntil is { } suspended && suspended > DateTimeOffset.Now)
                return ("일시 중지", "disabled");

            return Device.LastState switch
            {
                "Allowed" => ("사용 중", "allowed"),
                "Blocked" => ("차단", "blocked"),
                "Disabled" => ("제한 없음", "disabled"),
                _ => ("확인 중", "disabled")
            };
        }
    }

    public string LastSeenText
    {
        get
        {
            if (Device.LastSeenAt is not { } seen) return "연결된 적 없음";

            var elapsed = DateTimeOffset.Now - seen;

            if (elapsed < TimeSpan.FromMinutes(1)) return "방금 전";
            if (elapsed < TimeSpan.FromHours(1)) return $"{(int)elapsed.TotalMinutes}분 전";
            if (elapsed < TimeSpan.FromDays(1)) return $"{(int)elapsed.TotalHours}시간 전";

            return seen.Local("MM-dd HH:mm");
        }
    }

    public string PolicyText => Device.UsesDefaultPolicy ? "기본 시간표" : "전용 시간표";

    public static DeviceView From(Device device, int offlineAfterMinutes, int pendingRequests = 0) => new()
    {
        Device = device,
        Online = device.LastSeenAt is { } seen &&
                 DateTimeOffset.Now - seen < TimeSpan.FromMinutes(offlineAfterMinutes),
        PendingRequests = pendingRequests
    };
}

/// <summary>시간표를 화면에서 다루기 위한 도우미.</summary>
public static class ScheduleText
{
    public static readonly DayOfWeek[] WeekOrder =
    {
        DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday, DayOfWeek.Thursday,
        DayOfWeek.Friday, DayOfWeek.Saturday, DayOfWeek.Sunday
    };

    public static string KoreanDay(DayOfWeek day) => day switch
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

    /// <summary>하루치 구간을 "09:00-12:00, 13:00-18:00" 형태로 만든다.</summary>
    public static string Format(IReadOnlyList<TimeWindow> windows) =>
        windows.Count == 0 ? string.Empty : string.Join(", ", windows.Select(w => w.ToString()));

    /// <summary>화면에서 입력한 문자열을 구간 목록으로 바꾼다.</summary>
    public static bool TryParse(string? input, out List<TimeWindow> windows, out string error)
    {
        windows = new List<TimeWindow>();
        error = string.Empty;

        input = input?.Trim() ?? string.Empty;

        if (input.Length == 0 || input is "없음" or "-" or "금지")
            return true; // 사용 불가

        if (input is "종일" or "24시간")
        {
            windows.Add(new TimeWindow(TimeOnly.MinValue, TimeOnly.MinValue));
            return true;
        }

        foreach (var part in input.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!TimeWindow.TryParse(part, out var window))
            {
                error = $"'{part}' 를 알아볼 수 없습니다. 09:00-18:00 형식으로 입력해 주세요.";
                windows.Clear();
                return false;
            }

            windows.Add(window);
        }

        var sorted = windows.Where(w => !w.CrossesMidnight).OrderBy(w => w.Start).ToList();
        for (var i = 1; i < sorted.Count; i++)
        {
            if (sorted[i].Start < sorted[i - 1].End)
            {
                error = $"{sorted[i - 1]} 와 {sorted[i]} 구간이 서로 겹칩니다.";
                windows.Clear();
                return false;
            }
        }

        return true;
    }

    /// <summary>사용 불가인 날을 화면에 어떻게 쓸지.</summary>
    public const string BlockedText = "없음";
}
