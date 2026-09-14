using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace Hanil.TimeGuard.Server.Data;

/// <summary>
/// SQLite 는 DateTimeOffset 을 ORDER BY 에 쓰지 못한다.
/// 그래서 UTC 틱(100나노초 단위 정수)으로 저장한다. 정수라 정렬과 비교가 정확하다.
/// 읽을 때는 UTC 기준 DateTimeOffset 으로 돌아오므로, 화면에 보일 때 지역 시각으로 바꿔 준다.
/// </summary>
public sealed class UtcTicksConverter : ValueConverter<DateTimeOffset, long>
{
    public UtcTicksConverter()
        : base(value => value.ToUniversalTime().Ticks,
               ticks => new DateTimeOffset(ticks, TimeSpan.Zero))
    {
    }
}

public static class TimeText
{
    /// <summary>저장된 UTC 시각을 이 서버의 지역 시각으로 바꿔 표시한다.</summary>
    public static string Local(this DateTimeOffset value, string format) =>
        value.ToLocalTime().ToString(format);

    public static string Local(this DateTimeOffset? value, string format, string fallback = "-") =>
        value is { } actual ? actual.ToLocalTime().ToString(format) : fallback;
}
