using System.Text.Json.Serialization;

namespace Hanil.TimeGuard.Core.Config;

/// <summary>
/// 하루 안에서 PC 사용이 허용되는 한 구간.
/// End 가 Start 보다 이르면 자정을 넘겨 다음 날까지 이어지는 구간으로 본다(야간 근무 대응).
/// </summary>
public sealed class TimeWindow
{
    public TimeOnly Start { get; set; }
    public TimeOnly End { get; set; }

    public TimeWindow() { }

    public TimeWindow(TimeOnly start, TimeOnly end)
    {
        Start = start;
        End = end;
    }

    /// <summary>자정을 넘겨 다음 날로 이어지는 구간인지 여부.</summary>
    [JsonIgnore]
    public bool CrossesMidnight => End <= Start;

    /// <summary>구간의 실제 길이. 자정을 넘기면 다음 날 기준으로 계산한다.</summary>
    [JsonIgnore]
    public TimeSpan Duration =>
        CrossesMidnight
            ? TimeSpan.FromDays(1) - (Start - End)
            : End - Start;

    /// <summary>"09:00-18:00" 형태의 문자열을 구간으로 해석한다.</summary>
    public static bool TryParse(string? text, out TimeWindow window)
    {
        window = new TimeWindow();
        if (string.IsNullOrWhiteSpace(text)) return false;

        var parts = text.Split('-', '~');
        if (parts.Length != 2) return false;

        if (!TryParseTime(parts[0], out var start)) return false;
        if (!TryParseTime(parts[1], out var end)) return false;

        window = new TimeWindow(start, end);
        return true;
    }

    private static bool TryParseTime(string text, out TimeOnly value)
    {
        text = text.Trim();
        // 24:00 은 하루의 끝을 뜻하는 관용 표기이므로 00:00 으로 받아들인다.
        if (text is "24:00" or "2400")
        {
            value = TimeOnly.MinValue;
            return true;
        }
        return TimeOnly.TryParseExact(text, "HH:mm", out value)
            || TimeOnly.TryParseExact(text, "H:mm", out value)
            || TimeOnly.TryParseExact(text, "HHmm", out value);
    }

    public override string ToString() => $"{Start:HH\\:mm}-{End:HH\\:mm}";
}
