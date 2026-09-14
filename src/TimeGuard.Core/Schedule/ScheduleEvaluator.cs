using Hanil.TimeGuard.Core.Config;

namespace Hanil.TimeGuard.Core.Schedule;

/// <summary>
/// 설정과 현재 시각만으로 "지금 PC 를 써도 되는가"를 판정한다.
/// 부작용이 없는 순수 계산이라 단위 테스트로 전부 검증할 수 있다.
/// </summary>
public static class ScheduleEvaluator
{
    /// <summary>앞으로 며칠까지 다음 허용 구간을 찾아볼지.</summary>
    private const int LookAheadDays = 14;

    public static GuardDecision Evaluate(GuardConfig config, DateTimeOffset now, string? currentUser = null)
    {
        ArgumentNullException.ThrowIfNull(config);

        if (!config.Enabled)
            return GuardDecision.Disabled("감시 기능이 꺼져 있습니다.");

        if (config.SuspendedUntil is { } suspended && suspended > now)
            return GuardDecision.Disabled($"{suspended:yyyy-MM-dd HH:mm} 까지 일시 중지 중입니다.");

        if (currentUser is not null && IsExempt(config, currentUser))
            return GuardDecision.Disabled($"'{currentUser}' 계정은 제한 대상에서 제외되어 있습니다.");

        var windows = EnumerateWindows(config, now).ToList();
        var current = windows.FirstOrDefault(w => w.Start <= now && now < w.End);

        var extension = config.ExtensionUntil;
        var extensionActive = extension is { } ext && ext > now;

        if (current != default)
        {
            // 허용 구간 안. 연장이 구간 종료보다 뒤면 그만큼 늘려 준다.
            var effectiveEnd = current.End;
            var applied = false;

            if (extensionActive && extension!.Value > effectiveEnd)
            {
                effectiveEnd = extension.Value;
                applied = true;
            }

            return new GuardDecision
            {
                State = GuardState.Allowed,
                Remaining = effectiveEnd - now,
                WindowEnd = effectiveEnd,
                NextAllowedStart = null,
                ExtensionApplied = applied,
                Reason = applied
                    ? $"연장 적용으로 {effectiveEnd:HH:mm} 까지 사용 가능합니다."
                    : $"허용 시간대({current.Start:HH:mm}-{current.End:HH:mm}) 안입니다."
            };
        }

        if (extensionActive)
        {
            // 허용 구간 밖이지만 관리자가 연장을 부여한 상태.
            return new GuardDecision
            {
                State = GuardState.Allowed,
                Remaining = extension!.Value - now,
                WindowEnd = extension.Value,
                NextAllowedStart = null,
                ExtensionApplied = true,
                Reason = $"관리자 연장으로 {extension.Value:HH:mm} 까지 사용 가능합니다."
            };
        }

        var next = windows.Where(w => w.Start > now)
                          .OrderBy(w => w.Start)
                          .Select(w => (DateTimeOffset?)w.Start)
                          .FirstOrDefault();

        return new GuardDecision
        {
            State = GuardState.Blocked,
            Remaining = null,
            WindowEnd = null,
            NextAllowedStart = next,
            Reason = next is { } n
                ? $"허용 시간대가 아닙니다. 다음 사용 가능 시각: {n:yyyy-MM-dd HH:mm}"
                : "허용 시간대가 아닙니다. 예정된 사용 가능 시간이 없습니다."
        };
    }

    /// <summary>
    /// 남은 시간이 경고 단계에 해당하는지 확인한다.
    /// 반환값은 알려야 할 "분" 값이며, 해당 없으면 null.
    /// </summary>
    public static int? MatchNoticeMinute(WarningSettings warnings, TimeSpan remaining)
    {
        ArgumentNullException.ThrowIfNull(warnings);
        if (remaining < TimeSpan.Zero) return null;

        foreach (var minute in warnings.OrderedNoticeMinutes)
        {
            var threshold = TimeSpan.FromMinutes(minute);
            // 남은 시간이 임계값 이하로 막 떨어진 구간에서 한 번 잡아낸다.
            if (remaining <= threshold && remaining > threshold - TimeSpan.FromMinutes(1))
                return minute;
        }

        return null;
    }

    private static bool IsExempt(GuardConfig config, string user)
    {
        foreach (var exempt in config.ExemptUsers)
        {
            if (string.IsNullOrWhiteSpace(exempt)) continue;

            // "DOMAIN\user" 와 "user" 를 모두 허용한다.
            var normalized = exempt.Contains('\\') ? exempt[(exempt.IndexOf('\\') + 1)..] : exempt;
            var candidate = user.Contains('\\') ? user[(user.IndexOf('\\') + 1)..] : user;

            if (string.Equals(exempt, user, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(normalized, candidate, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    /// <summary>
    /// 어제부터 LookAheadDays 뒤까지의 모든 허용 구간을 실제 시각으로 펼친다.
    /// 어제부터 시작하는 이유는 자정을 넘겨 오늘 새벽까지 이어지는 구간을 놓치지 않기 위해서다.
    /// </summary>
    private static IEnumerable<(DateTimeOffset Start, DateTimeOffset End)> EnumerateWindows(
        GuardConfig config, DateTimeOffset now)
    {
        var offset = now.Offset;
        var today = DateOnly.FromDateTime(now.DateTime);

        for (var dayOffset = -1; dayOffset <= LookAheadDays; dayOffset++)
        {
            var date = today.AddDays(dayOffset);

            if (config.IsHoliday(date))
            {
                if (config.HolidayPolicy == HolidayPolicy.Blocked)
                    continue;

                // 휴일 무제한: 그날 하루를 통째로 허용 구간으로 본다.
                var dayStart = new DateTimeOffset(date.ToDateTime(TimeOnly.MinValue), offset);
                yield return (dayStart, dayStart.AddDays(1));
                continue;
            }

            foreach (var window in config.Schedule.ForDay(date.DayOfWeek))
            {
                if (window is null) continue;

                var start = new DateTimeOffset(date.ToDateTime(window.Start), offset);
                var end = window.CrossesMidnight
                    ? new DateTimeOffset(date.AddDays(1).ToDateTime(window.End), offset)
                    : new DateTimeOffset(date.ToDateTime(window.End), offset);

                if (end <= start) continue; // 길이가 0 인 구간은 무시
                yield return (start, end);
            }
        }
    }
}
