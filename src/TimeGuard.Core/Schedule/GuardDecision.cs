namespace Hanil.TimeGuard.Core.Schedule;

public enum GuardState
{
    /// <summary>감시가 꺼져 있거나 일시 중지 중. 아무 조치도 하지 않는다.</summary>
    Disabled = 0,
    /// <summary>허용 시간대 안. 사용 가능.</summary>
    Allowed = 1,
    /// <summary>허용 시간대 밖. 유예 시간이 지나면 조치한다.</summary>
    Blocked = 2
}

/// <summary>특정 시점에 대한 스케줄 판정 결과.</summary>
public sealed record GuardDecision
{
    public required GuardState State { get; init; }

    /// <summary>Allowed 인 경우 차단까지 남은 시간. Blocked 면 null.</summary>
    public TimeSpan? Remaining { get; init; }

    /// <summary>현재(또는 곧 시작할) 허용 구간의 종료 시각.</summary>
    public DateTimeOffset? WindowEnd { get; init; }

    /// <summary>Blocked 인 경우 다음으로 사용 가능해지는 시각. 예정이 없으면 null.</summary>
    public DateTimeOffset? NextAllowedStart { get; init; }

    /// <summary>판정 근거를 사람이 읽을 수 있게 적은 설명.</summary>
    public required string Reason { get; init; }

    /// <summary>연장 시간이 적용된 판정인지 여부.</summary>
    public bool ExtensionApplied { get; init; }

    public static GuardDecision Disabled(string reason) =>
        new() { State = GuardState.Disabled, Reason = reason };
}
