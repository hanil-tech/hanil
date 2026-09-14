using Hanil.TimeGuard.Core.Config;

namespace Hanil.TimeGuard.Core.Server;

/// <summary>서버와 클라이언트가 주고받는 내용. 양쪽이 같은 정의를 쓴다.</summary>
public static class ServerRoutes
{
    /// <summary>등록 키 없이 자기를 알리고 승인을 기다린다.</summary>
    public const string Announce = "/api/announce";

    /// <summary>승인되었는지 확인하고, 승인되었으면 토큰을 받아 온다.</summary>
    public const string Claim = "/api/claim";

    /// <summary>등록 키로 곧바로 등록한다. 여러 대를 한꺼번에 설치할 때 쓴다.</summary>
    public const string Enroll = "/api/enroll";
    public const string Heartbeat = "/api/heartbeat";
    public const string Events = "/api/events";
    public const string ExtensionRequests = "/api/extension-requests";
    public const string MyRequests = "/api/extension-requests/mine";

    /// <summary>장비 토큰을 실어 보내는 헤더 이름.</summary>
    public const string TokenHeader = "X-TimeGuard-Token";
}

/// <summary>
/// 직원 PC 가 서버에 자기를 알린다.
///
/// 등록 키가 필요 없다. 관리자가 서버 화면에서 승인해야 실제로 등록된다.
/// 승인 전에는 아무 정책도 받지 못한다.
/// </summary>
public sealed class AnnounceRequest
{
    public string MachineName { get; set; } = string.Empty;
    public string OsUser { get; set; } = string.Empty;

    /// <summary>
    /// 이 PC 가 스스로 만들어 보관하는 비밀값.
    /// 나중에 토큰을 받아 갈 때 자기가 맞다는 것을 증명하는 데 쓴다.
    /// 관리자가 받아 적을 일이 없도록 자동으로 만들어진다.
    /// </summary>
    public string ClientId { get; set; } = string.Empty;

    public string ClientVersion { get; set; } = string.Empty;
}

public sealed class AnnounceResponse
{
    /// <summary>지금 어떤 상태인지. Pending / Approved / Rejected.</summary>
    public string State { get; set; } = string.Empty;

    /// <summary>관리자가 알아보기 쉽도록 보여 줄 짧은 확인 문자.</summary>
    public string Fingerprint { get; set; } = string.Empty;

    /// <summary>사람이 읽을 안내 문구.</summary>
    public string Message { get; set; } = string.Empty;
}

/// <summary>승인되었는지 확인하고 토큰을 받아 온다.</summary>
public sealed class ClaimRequest
{
    public string ClientId { get; set; } = string.Empty;
    public string MachineName { get; set; } = string.Empty;
}

public sealed class ClaimResponse
{
    public string State { get; set; } = string.Empty;

    /// <summary>승인된 경우에만 채워진다.</summary>
    public string? DeviceId { get; set; }
    public string? Token { get; set; }
    public string? DisplayName { get; set; }

    public string Message { get; set; } = string.Empty;
}

/// <summary>승인 상태.</summary>
public static class ApprovalStates
{
    public const string Pending = "Pending";
    public const string Approved = "Approved";
    public const string Rejected = "Rejected";
}

/// <summary>최초 등록 요청.</summary>
public sealed class EnrollRequest
{
    public string MachineName { get; set; } = string.Empty;
    public string OsUser { get; set; } = string.Empty;

    /// <summary>서버 설정에 있는 등록 키. 아무 PC 나 등록되지 않도록 확인한다.</summary>
    public string EnrollmentKey { get; set; } = string.Empty;

    /// <summary>이미 등록된 적이 있으면 그 식별자를 보내 재등록을 시도한다.</summary>
    public string? ExistingDeviceId { get; set; }
}

public sealed class EnrollResponse
{
    public string DeviceId { get; set; } = string.Empty;

    /// <summary>이후 모든 요청에 실어 보낼 토큰. 서버는 해시만 저장한다.</summary>
    public string Token { get; set; } = string.Empty;

    public string DisplayName { get; set; } = string.Empty;
}

/// <summary>주기적으로 보내는 생존 신호이자 정책 요청.</summary>
public sealed class HeartbeatRequest
{
    /// <summary>클라이언트가 지금 적용 중인 정책의 표식. 서버 값과 같으면 정책을 다시 안 보낸다.</summary>
    public string? PolicyStamp { get; set; }

    public string State { get; set; } = string.Empty;
    public string Reason { get; set; } = string.Empty;
    public string OsUser { get; set; } = string.Empty;
    public double? RemainingSeconds { get; set; }
    public string ClientVersion { get; set; } = string.Empty;

    /// <summary>
    /// 지금 로그인한 계정이 이 PC 의 관리자인지.
    ///
    /// 관리자면 서비스를 멈춰 제한을 무력화할 수 있으므로,
    /// 관리자가 어느 PC 를 손봐야 하는지 알 수 있도록 함께 보고한다.
    /// 확인하지 못했으면 null.
    /// </summary>
    public bool? UserIsAdministrator { get; set; }
}

public sealed class HeartbeatResponse
{
    public DateTimeOffset ServerTime { get; set; }

    /// <summary>서버가 보는 현재 정책 표식.</summary>
    public string PolicyStamp { get; set; } = string.Empty;

    /// <summary>정책이 바뀐 경우에만 채워진다. 같으면 null 이라 통신량이 적다.</summary>
    public GuardConfig? Policy { get; set; }

    /// <summary>연장과 일시 중지는 자주 바뀌므로 정책과 별개로 매번 내려보낸다.</summary>
    public DateTimeOffset? ExtensionUntil { get; set; }
    public DateTimeOffset? SuspendedUntil { get; set; }

    /// <summary>관리자가 이 PC 의 제한을 꺼 두었는지.</summary>
    public bool Enforced { get; set; }

    /// <summary>관리자가 붙인 이름. 클라이언트 화면에 보여 준다.</summary>
    public string DisplayName { get; set; } = string.Empty;

    /// <summary>사용자에게 알려 줄 연장 요청 처리 결과. 없으면 비어 있다.</summary>
    public List<RequestDecision> Decisions { get; set; } = new();
}

/// <summary>처리된 연장 요청 한 건.</summary>
public sealed class RequestDecision
{
    public int RequestId { get; set; }
    public string Status { get; set; } = string.Empty;
    public int? GrantedMinutes { get; set; }
    public DateTimeOffset? GrantedUntil { get; set; }
    public string? Note { get; set; }
    public DateTimeOffset DecidedAt { get; set; }
}

/// <summary>클라이언트가 모아서 올리는 사건 기록.</summary>
public sealed class EventReport
{
    public List<EventEntry> Entries { get; set; } = new();
}

public sealed class EventEntry
{
    public DateTimeOffset At { get; set; }
    public string Category { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}

/// <summary>직원이 올리는 사용 시간 연장 요청.</summary>
public sealed class ExtensionRequestInput
{
    public int Minutes { get; set; }
    public string Reason { get; set; } = string.Empty;
    public string OsUser { get; set; } = string.Empty;
}

public sealed class ExtensionRequestCreated
{
    public int RequestId { get; set; }
    public string Message { get; set; } = string.Empty;
}

/// <summary>서버가 오류를 알릴 때 쓰는 형식.</summary>
public sealed class ApiError
{
    public string Message { get; set; } = string.Empty;

    public static ApiError From(string message) => new() { Message = message };
}
