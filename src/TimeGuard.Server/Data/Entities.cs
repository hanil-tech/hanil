using System.ComponentModel.DataAnnotations;

namespace Hanil.TimeGuard.Server.Data;

/// <summary>PC 가 관리 대상으로 승인되었는지.</summary>
public enum ApprovalState
{
    /// <summary>발견되었지만 아직 관리자가 승인하지 않았다. 아무 정책도 주지 않는다.</summary>
    Pending = 0,

    /// <summary>관리자가 승인했다. 정상 동작한다.</summary>
    Approved = 1,

    /// <summary>관리자가 거절했다. 목록에 다시 나타나지 않는다.</summary>
    Rejected = 2
}

/// <summary>관리 대상 PC 한 대.</summary>
public sealed class Device
{
    /// <summary>승인 상태. 승인 전에는 시간표를 받아 갈 수 없다.</summary>
    public ApprovalState Approval { get; set; } = ApprovalState.Approved;

    /// <summary>
    /// 이 PC 가 스스로 만든 비밀값의 해시.
    /// 승인된 뒤 토큰을 받아 갈 때 자기가 맞다는 것을 확인하는 데 쓴다.
    /// </summary>
    public string ClientIdHash { get; set; } = string.Empty;

    /// <summary>관리자가 화면에서 알아볼 수 있게 보여 줄 짧은 문자.</summary>
    public string Fingerprint { get; set; } = string.Empty;

    /// <summary>처음 발견된 시각.</summary>
    public DateTimeOffset? AnnouncedAt { get; set; }

    /// <summary>알림이 들어온 주소. 어느 PC 인지 가늠하는 데 쓴다.</summary>
    public string AnnouncedFrom { get; set; } = string.Empty;

    /// <summary>승인하거나 거절한 사람과 시각.</summary>
    public DateTimeOffset? DecidedAt { get; set; }
    public string DecidedBy { get; set; } = string.Empty;

    /// <summary>등록할 때 서버가 발급하는 식별자.</summary>
    [Key]
    public string Id { get; set; } = Guid.NewGuid().ToString("N");

    /// <summary>PC 이름(컴퓨터 이름). 관리자가 알아보기 위한 값이다.</summary>
    public string MachineName { get; set; } = string.Empty;

    /// <summary>관리자가 붙인 이름. 예: "생산1팀 홍길동".</summary>
    public string DisplayName { get; set; } = string.Empty;

    /// <summary>마지막으로 로그인한 Windows 사용자.</summary>
    public string LastUser { get; set; } = string.Empty;

    /// <summary>장비 인증 토큰의 해시. 원본은 클라이언트에만 있다.</summary>
    public string TokenHash { get; set; } = string.Empty;

    public DateTimeOffset EnrolledAt { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset? LastSeenAt { get; set; }

    /// <summary>
    /// 마지막으로 로그인한 계정이 이 PC 의 관리자인지.
    /// 관리자면 서비스를 멈춰 제한을 무력화할 수 있으므로 화면에 눈에 띄게 알린다.
    /// </summary>
    public bool? LastUserIsAdministrator { get; set; }

    /// <summary>클라이언트가 마지막으로 보고한 판정 상태.</summary>
    public string LastState { get; set; } = string.Empty;
    public string LastReason { get; set; } = string.Empty;

    /// <summary>이 PC 에 제한을 적용할지 여부. 끄면 서버가 "제한 없음" 정책을 내려보낸다.</summary>
    public bool Enforced { get; set; } = true;

    /// <summary>true 면 기본 정책을 따르고, false 면 이 PC 전용 시간표를 쓴다.</summary>
    public bool UsesDefaultPolicy { get; set; } = true;

    /// <summary>이 PC 전용 시간표(JSON). UsesDefaultPolicy 가 false 일 때만 쓰인다.</summary>
    public string? CustomScheduleJson { get; set; }

    /// <summary>관리자가 부여한 연장의 만료 시각.</summary>
    public DateTimeOffset? ExtensionUntil { get; set; }

    /// <summary>관리자가 건 일시 중지의 만료 시각.</summary>
    public DateTimeOffset? SuspendedUntil { get; set; }

    public string Note { get; set; } = string.Empty;

    /// <summary>정책이 바뀔 때마다 올라간다. 클라이언트는 이 값이 달라질 때만 새로 받는다.</summary>
    public long PolicyVersion { get; set; } = 1;
}

/// <summary>기본 정책. 모든 PC 가 기본으로 따르는 시간표와 조치 설정.</summary>
public sealed class DefaultPolicy
{
    [Key]
    public int Id { get; set; } = 1;

    /// <summary>요일별 허용 시간대(JSON).</summary>
    public string ScheduleJson { get; set; } = string.Empty;

    /// <summary>시간 초과 시 조치.</summary>
    public string Action { get; set; } = "Shutdown";

    /// <summary>경고 단계 설정(JSON).</summary>
    public string WarningsJson { get; set; } = string.Empty;

    /// <summary>지정 휴일(JSON 배열).</summary>
    public string HolidaysJson { get; set; } = "[]";

    public string HolidayPolicy { get; set; } = "Blocked";

    /// <summary>제한을 적용하지 않을 Windows 계정(JSON 배열).</summary>
    public string ExemptUsersJson { get; set; } = "[]";

    /// <summary>차단 중에 원격 데스크톱 접속을 막을지.</summary>
    public bool BlockRemoteAccess { get; set; }

    /// <summary>차단 중에 원격 제어 프로그램(팀뷰어 등)을 막을지.</summary>
    public bool BlockRemoteTools { get; set; }

    /// <summary>기본 목록에 더해 막을 프로그램 이름(JSON 배열).</summary>
    public string ExtraRemoteToolNamesJson { get; set; } = "[]";

    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.Now;
    public string UpdatedBy { get; set; } = string.Empty;

    public long Version { get; set; } = 1;
}

public enum RequestStatus
{
    Pending = 0,
    Approved = 1,
    Denied = 2,
    Cancelled = 3
}

/// <summary>직원이 올린 사용 시간 연장 요청.</summary>
public sealed class ExtensionRequest
{
    [Key]
    public int Id { get; set; }

    public string DeviceId { get; set; } = string.Empty;
    public Device? Device { get; set; }

    /// <summary>요청한 분 수.</summary>
    public int RequestedMinutes { get; set; }

    /// <summary>요청 사유.</summary>
    public string Reason { get; set; } = string.Empty;

    /// <summary>요청한 Windows 사용자.</summary>
    public string RequestedBy { get; set; } = string.Empty;

    public DateTimeOffset RequestedAt { get; set; } = DateTimeOffset.Now;

    public RequestStatus Status { get; set; } = RequestStatus.Pending;

    /// <summary>관리자가 실제로 승인한 분 수. 요청보다 적게 줄 수도 있다.</summary>
    public int? GrantedMinutes { get; set; }

    public DateTimeOffset? GrantedUntil { get; set; }
    public DateTimeOffset? DecidedAt { get; set; }
    public string? DecidedBy { get; set; }

    /// <summary>
    /// 처리 결과를 해당 PC 에 전달한 시각.
    /// 이 값이 비어 있는 건만 내려보내므로 같은 알림이 반복되지 않는다.
    /// </summary>
    public DateTimeOffset? NotifiedAt { get; set; }

    /// <summary>거절 사유 등 관리자가 남긴 말.</summary>
    public string? DecisionNote { get; set; }
}

/// <summary>클라이언트가 보고한 사건(전원 차단, 서비스 시작 등).</summary>
public sealed class DeviceEvent
{
    [Key]
    public long Id { get; set; }

    public string DeviceId { get; set; } = string.Empty;
    public Device? Device { get; set; }

    public DateTimeOffset At { get; set; } = DateTimeOffset.Now;

    /// <summary>"조치", "경고", "서비스", "설정" 등.</summary>
    public string Category { get; set; } = string.Empty;

    public string Message { get; set; } = string.Empty;
}

/// <summary>웹 화면에 로그인하는 관리자.</summary>
public sealed class AdminUser
{
    [Key]
    public int Id { get; set; }

    public string UserName { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset? LastLoginAt { get; set; }
}

/// <summary>서버 전역 설정(등록 키 등).</summary>
public sealed class ServerSetting
{
    [Key]
    public string Key { get; set; } = string.Empty;
    public string Value { get; set; } = string.Empty;
}
