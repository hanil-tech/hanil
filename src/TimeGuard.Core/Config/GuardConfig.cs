namespace Hanil.TimeGuard.Core.Config;

/// <summary>시간 초과 시 수행할 동작.</summary>
public enum GuardAction
{
    /// <summary>컴퓨터 전원 차단.</summary>
    Shutdown = 0,
    /// <summary>사용자 로그오프.</summary>
    LogOff = 1,
    /// <summary>화면 잠금(가장 약한 조치).</summary>
    Lock = 2
}

/// <summary>지정 휴일의 처리 방식.</summary>
public enum HolidayPolicy
{
    /// <summary>휴일에는 사용 불가.</summary>
    Blocked = 0,
    /// <summary>휴일에는 제한 없음.</summary>
    Unrestricted = 1
}

public sealed class GuardConfig
{
    /// <summary>설정 파일 형식 버전. 앞으로의 마이그레이션에 사용한다.</summary>
    public int Version { get; set; } = 1;

    /// <summary>전체 기능 사용 여부. false 면 감시만 하고 아무 조치도 하지 않는다.</summary>
    public bool Enabled { get; set; } = false;

    /// <summary>관리자 비밀번호 해시(PBKDF2). 비어 있으면 최초 설정이 필요한 상태.</summary>
    public string PasswordHash { get; set; } = string.Empty;

    /// <summary>시간 초과 시 동작.</summary>
    public GuardAction Action { get; set; } = GuardAction.Shutdown;

    /// <summary>요일별 허용 시간대.</summary>
    public WeeklySchedule Schedule { get; set; } = WeeklySchedule.CreateDefault();

    /// <summary>경고 및 유예 설정.</summary>
    public WarningSettings Warnings { get; set; } = new();

    /// <summary>지정 휴일(yyyy-MM-dd).</summary>
    public List<string> Holidays { get; set; } = new();

    /// <summary>휴일 처리 방식.</summary>
    public HolidayPolicy HolidayPolicy { get; set; } = HolidayPolicy.Blocked;

    /// <summary>이 시각까지 감시를 일시 중지한다(관리자 작업 시간 등).</summary>
    public DateTimeOffset? SuspendedUntil { get; set; }

    /// <summary>오늘 한 번만 이 시각까지 사용을 연장한다.</summary>
    public DateTimeOffset? ExtensionUntil { get; set; }

    /// <summary>제한을 적용하지 않을 Windows 계정 이름 목록(관리자 계정 등).</summary>
    public List<string> ExemptUsers { get; set; } = new();

    /// <summary>마지막 수정 시각과 수정자.</summary>
    public DateTimeOffset LastModified { get; set; } = DateTimeOffset.Now;
    public string LastModifiedBy { get; set; } = string.Empty;

    /// <summary>지정된 날짜가 휴일인지 확인한다.</summary>
    public bool IsHoliday(DateOnly date) =>
        Holidays.Contains(date.ToString("yyyy-MM-dd"));

    public void AddHoliday(DateOnly date)
    {
        var key = date.ToString("yyyy-MM-dd");
        if (!Holidays.Contains(key)) Holidays.Add(key);
        Holidays.Sort(StringComparer.Ordinal);
    }

    public void RemoveHoliday(DateOnly date) =>
        Holidays.Remove(date.ToString("yyyy-MM-dd"));

    /// <summary>최초 설치 직후의 안전한 상태. 비밀번호가 정해지기 전에는 차단하지 않는다.</summary>
    public static GuardConfig CreateInitial() => new()
    {
        Enabled = false,
        Schedule = WeeklySchedule.CreateDefault(),
        Action = GuardAction.Shutdown
    };
}

/// <summary>차단 전 경고 단계와 유예 시간.</summary>
public sealed class WarningSettings
{
    /// <summary>알림을 띄울 남은 시간(분). 큰 값부터 순서대로 정렬해 사용한다.</summary>
    public List<int> NoticeMinutes { get; set; } = new() { 10, 5, 1 };

    /// <summary>마지막 카운트다운 창을 띄울 남은 시간(초).</summary>
    public int CountdownSeconds { get; set; } = 60;

    /// <summary>허용 시간대 밖에서 PC 가 켜졌을 때 주는 유예 시간(초).</summary>
    public int OutsideWindowGraceSeconds { get; set; } = 120;

    /// <summary>사용자에게 표시할 안내 문구.</summary>
    public string Message { get; set; } = "허용된 사용 시간이 끝났습니다. 작업 중인 내용을 저장해 주세요.";

    public IEnumerable<int> OrderedNoticeMinutes =>
        NoticeMinutes.Where(m => m > 0).Distinct().OrderByDescending(m => m);
}
