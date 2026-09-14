namespace Hanil.TimeGuard.Core.Config;

/// <summary>요일별 허용 시간대 모음.</summary>
public sealed class WeeklySchedule
{
    /// <summary>요일 이름("Monday" 등)을 키로 하는 허용 구간 목록.</summary>
    public Dictionary<string, List<TimeWindow>> Days { get; set; } = new(StringComparer.OrdinalIgnoreCase);

    public IReadOnlyList<TimeWindow> ForDay(DayOfWeek day) =>
        Days.TryGetValue(day.ToString(), out var windows) && windows is not null
            ? windows
            : Array.Empty<TimeWindow>();

    public void SetDay(DayOfWeek day, IEnumerable<TimeWindow> windows) =>
        Days[day.ToString()] = windows.OrderBy(w => w.Start).ToList();

    public void ClearDay(DayOfWeek day) => Days[day.ToString()] = new List<TimeWindow>();

    /// <summary>평일 09:00-18:00, 주말 사용 불가 기본값.</summary>
    public static WeeklySchedule CreateDefault()
    {
        var schedule = new WeeklySchedule();
        var office = new List<TimeWindow> { new(new TimeOnly(9, 0), new TimeOnly(18, 0)) };

        foreach (var day in new[]
                 {
                     DayOfWeek.Monday, DayOfWeek.Tuesday, DayOfWeek.Wednesday,
                     DayOfWeek.Thursday, DayOfWeek.Friday
                 })
        {
            schedule.SetDay(day, office.Select(w => new TimeWindow(w.Start, w.End)));
        }

        schedule.ClearDay(DayOfWeek.Saturday);
        schedule.ClearDay(DayOfWeek.Sunday);
        return schedule;
    }

    /// <summary>모든 요일 24시간 허용. 설정이 완료될 때까지 잠그지 않기 위한 안전 기본값.</summary>
    public static WeeklySchedule CreateUnrestricted()
    {
        var schedule = new WeeklySchedule();
        foreach (DayOfWeek day in Enum.GetValues<DayOfWeek>())
        {
            schedule.SetDay(day, new[] { new TimeWindow(TimeOnly.MinValue, TimeOnly.MinValue) });
        }
        return schedule;
    }
}
