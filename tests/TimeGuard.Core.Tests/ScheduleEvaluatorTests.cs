using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Schedule;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

public class ScheduleEvaluatorTests
{
    private static readonly TimeSpan Kst = TimeSpan.FromHours(9);

    private static DateTimeOffset At(int year, int month, int day, int hour, int minute, int second = 0) =>
        new(year, month, day, hour, minute, second, Kst);

    private static GuardConfig OfficeHours()
    {
        var config = GuardConfig.CreateInitial();
        config.Enabled = true;
        config.PasswordHash = "pbkdf2$1$AAAA$BBBB";
        config.Schedule = WeeklySchedule.CreateDefault(); // 평일 09:00-18:00
        return config;
    }

    // 2026-09-14 는 월요일, 2026-09-19 는 토요일이다.

    [Fact]
    public void 허용_시간대_안이면_사용_가능하다()
    {
        var decision = ScheduleEvaluator.Evaluate(OfficeHours(), At(2026, 9, 14, 10, 0));

        Assert.Equal(GuardState.Allowed, decision.State);
        Assert.Equal(TimeSpan.FromHours(8), decision.Remaining);
    }

    [Fact]
    public void 허용_시간대_시작_직전은_차단된다()
    {
        var decision = ScheduleEvaluator.Evaluate(OfficeHours(), At(2026, 9, 14, 8, 59));

        Assert.Equal(GuardState.Blocked, decision.State);
        Assert.Equal(At(2026, 9, 14, 9, 0), decision.NextAllowedStart);
    }

    [Fact]
    public void 허용_시간대_종료_직후는_차단된다()
    {
        var decision = ScheduleEvaluator.Evaluate(OfficeHours(), At(2026, 9, 14, 18, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
        Assert.Equal(At(2026, 9, 15, 9, 0), decision.NextAllowedStart);
    }

    [Fact]
    public void 주말은_차단되고_다음_평일을_안내한다()
    {
        var decision = ScheduleEvaluator.Evaluate(OfficeHours(), At(2026, 9, 19, 12, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
        Assert.Equal(At(2026, 9, 21, 9, 0), decision.NextAllowedStart); // 월요일
    }

    [Fact]
    public void 감시가_꺼져_있으면_판정하지_않는다()
    {
        var config = OfficeHours();
        config.Enabled = false;

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 19, 3, 0));

        Assert.Equal(GuardState.Disabled, decision.State);
    }

    [Fact]
    public void 일시_중지_기간에는_차단하지_않는다()
    {
        var config = OfficeHours();
        config.SuspendedUntil = At(2026, 9, 14, 23, 0);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 22, 0));

        Assert.Equal(GuardState.Disabled, decision.State);
    }

    [Fact]
    public void 일시_중지가_끝나면_다시_차단된다()
    {
        var config = OfficeHours();
        config.SuspendedUntil = At(2026, 9, 14, 21, 0);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 22, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
    }

    [Fact]
    public void 제외_계정은_제한받지_않는다()
    {
        var config = OfficeHours();
        config.ExemptUsers.Add("admin");

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 19, 3, 0), "HANIL\\admin");

        Assert.Equal(GuardState.Disabled, decision.State);
    }

    [Fact]
    public void 제외_계정이_아니면_그대로_차단된다()
    {
        var config = OfficeHours();
        config.ExemptUsers.Add("admin");

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 19, 3, 0), "HANIL\\worker1");

        Assert.Equal(GuardState.Blocked, decision.State);
    }

    [Fact]
    public void 연장은_차단_상태를_사용_가능으로_바꾼다()
    {
        var config = OfficeHours();
        config.ExtensionUntil = At(2026, 9, 14, 19, 0);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 18, 30));

        Assert.Equal(GuardState.Allowed, decision.State);
        Assert.True(decision.ExtensionApplied);
        Assert.Equal(TimeSpan.FromMinutes(30), decision.Remaining);
    }

    [Fact]
    public void 연장은_허용_구간_종료_시각도_늘린다()
    {
        var config = OfficeHours();
        config.ExtensionUntil = At(2026, 9, 14, 20, 0);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 17, 0));

        Assert.Equal(GuardState.Allowed, decision.State);
        Assert.True(decision.ExtensionApplied);
        Assert.Equal(At(2026, 9, 14, 20, 0), decision.WindowEnd);
    }

    [Fact]
    public void 지난_연장은_효력이_없다()
    {
        var config = OfficeHours();
        config.ExtensionUntil = At(2026, 9, 14, 18, 30);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 19, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
    }

    [Fact]
    public void 자정을_넘기는_야간_구간을_처리한다()
    {
        var config = OfficeHours();
        config.Schedule = new WeeklySchedule();
        // 월요일 22:00 시작해 화요일 06:00 종료
        config.Schedule.SetDay(DayOfWeek.Monday, new[] { new TimeWindow(new TimeOnly(22, 0), new TimeOnly(6, 0)) });

        var duringNight = ScheduleEvaluator.Evaluate(config, At(2026, 9, 15, 2, 0)); // 화요일 새벽 2시
        Assert.Equal(GuardState.Allowed, duringNight.State);
        Assert.Equal(TimeSpan.FromHours(4), duringNight.Remaining);

        var afterNight = ScheduleEvaluator.Evaluate(config, At(2026, 9, 15, 6, 1));
        Assert.Equal(GuardState.Blocked, afterNight.State);
    }

    [Fact]
    public void 하루에_두_구간을_둘_수_있다()
    {
        var config = OfficeHours();
        config.Schedule.SetDay(DayOfWeek.Monday, new[]
        {
            new TimeWindow(new TimeOnly(9, 0), new TimeOnly(12, 0)),
            new TimeWindow(new TimeOnly(13, 0), new TimeOnly(18, 0))
        });

        Assert.Equal(GuardState.Allowed, ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 11, 0)).State);
        Assert.Equal(GuardState.Blocked, ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 12, 30)).State);
        Assert.Equal(GuardState.Allowed, ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 14, 0)).State);
    }

    [Fact]
    public void 점심시간_차단_구간의_다음_시작을_안내한다()
    {
        var config = OfficeHours();
        config.Schedule.SetDay(DayOfWeek.Monday, new[]
        {
            new TimeWindow(new TimeOnly(9, 0), new TimeOnly(12, 0)),
            new TimeWindow(new TimeOnly(13, 0), new TimeOnly(18, 0))
        });

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 12, 30));

        Assert.Equal(At(2026, 9, 14, 13, 0), decision.NextAllowedStart);
    }

    [Fact]
    public void 휴일로_지정하면_평일이어도_차단된다()
    {
        var config = OfficeHours();
        config.AddHoliday(new DateOnly(2026, 9, 14));

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 10, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
        Assert.Equal(At(2026, 9, 15, 9, 0), decision.NextAllowedStart);
    }

    [Fact]
    public void 휴일_무제한_정책이면_휴일에_종일_사용할_수_있다()
    {
        var config = OfficeHours();
        config.HolidayPolicy = HolidayPolicy.Unrestricted;
        config.AddHoliday(new DateOnly(2026, 9, 19)); // 토요일

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 19, 3, 0));

        Assert.Equal(GuardState.Allowed, decision.State);
    }

    [Fact]
    public void 예정된_허용_구간이_전혀_없으면_다음_시각은_비어_있다()
    {
        var config = OfficeHours();
        config.Schedule = new WeeklySchedule();
        foreach (DayOfWeek day in Enum.GetValues<DayOfWeek>()) config.Schedule.ClearDay(day);

        var decision = ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 10, 0));

        Assert.Equal(GuardState.Blocked, decision.State);
        Assert.Null(decision.NextAllowedStart);
    }

    [Fact]
    public void 종일_허용_설정은_항상_사용_가능하다()
    {
        var config = OfficeHours();
        config.Schedule = WeeklySchedule.CreateUnrestricted();

        Assert.Equal(GuardState.Allowed, ScheduleEvaluator.Evaluate(config, At(2026, 9, 19, 3, 0)).State);
        Assert.Equal(GuardState.Allowed, ScheduleEvaluator.Evaluate(config, At(2026, 9, 14, 23, 59)).State);
    }

    [Theory]
    [InlineData(10.0, 10)]   // 정확히 10분 남음
    [InlineData(9.5, 10)]    // 10분 구간 안
    [InlineData(9.0, null)]  // 10분 구간을 지나고 5분에는 못 미침
    [InlineData(5.0, 5)]
    [InlineData(1.0, 1)]
    [InlineData(0.5, 1)]
    [InlineData(30.0, null)]
    public void 남은_시간에_맞는_경고_단계를_고른다(double remainingMinutes, int? expected)
    {
        var warnings = new WarningSettings();

        var actual = ScheduleEvaluator.MatchNoticeMinute(warnings, TimeSpan.FromMinutes(remainingMinutes));

        Assert.Equal(expected, actual);
    }

    [Fact]
    public void 남은_시간이_음수면_경고_단계가_없다()
    {
        var actual = ScheduleEvaluator.MatchNoticeMinute(new WarningSettings(), TimeSpan.FromMinutes(-1));

        Assert.Null(actual);
    }
}
