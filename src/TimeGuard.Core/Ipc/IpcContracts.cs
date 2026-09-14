using System.Text.Json;
using System.Text.Json.Serialization;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Schedule;

namespace Hanil.TimeGuard.Core.Ipc;

public static class IpcNames
{
    /// <summary>서비스가 여는 이름 있는 파이프. 에이전트와 관리자 도구가 여기에 연결한다.</summary>
    public const string PipeName = "HanilTimeGuard.Control";

    /// <summary>서비스 이름.</summary>
    public const string ServiceName = "HanilTimeGuard";
}

public static class IpcCommands
{
    public const string Ping = "PING";
    public const string Status = "STATUS";
    public const string GetConfig = "GET_CONFIG";
    public const string SetConfig = "SET_CONFIG";
    public const string SetPassword = "SET_PASSWORD";
    public const string Extend = "EXTEND";
    public const string Suspend = "SUSPEND";
    public const string SetEnabled = "SET_ENABLED";
    public const string GetLog = "GET_LOG";
    public const string CancelShutdown = "CANCEL_SHUTDOWN";

    /// <summary>사용자가 관리자에게 사용 시간 연장을 요청한다. 비밀번호가 필요 없다.</summary>
    public const string RequestExtension = "REQUEST_EXTENSION";
}

public sealed class IpcRequest
{
    public string Command { get; set; } = string.Empty;

    /// <summary>설정 변경 계열 명령에 필요한 관리자 비밀번호.</summary>
    public string? Password { get; set; }

    /// <summary>명령별 추가 인자를 담은 JSON.</summary>
    public string? Payload { get; set; }
}

public sealed class IpcResponse
{
    public bool Ok { get; set; }
    public string? Error { get; set; }
    public string? Payload { get; set; }

    public static IpcResponse Fail(string error) => new() { Ok = false, Error = error };
    public static IpcResponse Success(string? payload = null) => new() { Ok = true, Payload = payload };
}

/// <summary>에이전트와 관리자 도구에 전달하는 현재 상태 요약.</summary>
public sealed class StatusSnapshot
{
    public GuardState State { get; set; }
    public string Reason { get; set; } = string.Empty;
    public bool Enabled { get; set; }
    public GuardAction Action { get; set; }

    /// <summary>차단까지 남은 시간(초). 해당 없으면 null.</summary>
    public double? RemainingSeconds { get; set; }

    public DateTimeOffset? WindowEnd { get; set; }
    public DateTimeOffset? NextAllowedStart { get; set; }
    public DateTimeOffset? SuspendedUntil { get; set; }
    public DateTimeOffset? ExtensionUntil { get; set; }
    public bool ExtensionApplied { get; set; }

    /// <summary>사용자에게 보여 줄 안내 문구.</summary>
    public string Message { get; set; } = string.Empty;

    /// <summary>지금 띄워야 할 경고 단계(분). 없으면 null.</summary>
    public int? NoticeMinutes { get; set; }

    /// <summary>
    /// 경고마다 1씩 늘어나는 번호. 에이전트는 이 번호로 같은 경고를 두 번 띄우지 않는다.
    /// 서비스와 에이전트가 각자 1초 주기로 돌기 때문에 경고를 한 틱만 켜 두면 놓칠 수 있어,
    /// 서비스는 이 번호를 몇 초 동안 유지해 준다.
    /// </summary>
    public long NoticeId { get; set; }

    /// <summary>마지막 카운트다운이 진행 중인지와 남은 초.</summary>
    public bool CountdownActive { get; set; }
    public int CountdownSecondsLeft { get; set; }

    public DateTimeOffset ServerTime { get; set; }
    public string? Warning { get; set; }

    // --- 관리 서버 ---

    /// <summary>관리 서버가 설정되어 있는지. 이 경우 설정은 서버에서만 바꿀 수 있다.</summary>
    public bool ServerMode { get; set; }

    /// <summary>서버와 연락이 되고 있는지. 끊겨도 마지막 정책은 계속 적용된다.</summary>
    public bool ServerReachable { get; set; }

    public string? ServerUrl { get; set; }

    /// <summary>사용자에게 알려야 할 연장 요청 처리 결과. 없으면 null.</summary>
    public Server.RequestDecision? Decision { get; set; }
}

/// <summary>사용자가 올리는 연장 요청.</summary>
public sealed class UserExtensionRequest
{
    public int Minutes { get; set; }
    public string Reason { get; set; } = string.Empty;
}

/// <summary>EXTEND 명령 인자.</summary>
public sealed class ExtendRequest
{
    public int Minutes { get; set; }
}

/// <summary>SUSPEND 명령 인자.</summary>
public sealed class SuspendRequest
{
    /// <summary>0 이하면 일시 중지를 해제한다.</summary>
    public int Minutes { get; set; }
}

public sealed class SetEnabledRequest
{
    public bool Enabled { get; set; }
}

public sealed class SetPasswordRequest
{
    public string NewPassword { get; set; } = string.Empty;
}

public sealed class GetLogRequest
{
    public int Lines { get; set; } = 50;
}

public static class IpcJson
{
    public static readonly JsonSerializerOptions Options = CreateOptions();

    /// <summary>
    /// 통신과 설정 파일이 같은 형식을 쓰도록 한곳에서 만든다.
    /// 서버의 HTTP 응답도 이 설정을 그대로 쓴다.
    /// </summary>
    public static JsonSerializerOptions CreateOptions() => new()
    {
        WriteIndented = false,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        Converters =
        {
            new JsonStringEnumConverter(),
            new Config.TimeOnlyConverter()
        },
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    /// <summary>이미 만들어진 설정의 변환기와 규칙을 다른 설정에 그대로 옮긴다.</summary>
    public static void ApplyTo(JsonSerializerOptions target)
    {
        target.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
        target.Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping;

        target.Converters.Add(new JsonStringEnumConverter());
        target.Converters.Add(new Config.TimeOnlyConverter());
    }

    public static string Serialize<T>(T value) => JsonSerializer.Serialize(value, Options);

    public static T? Deserialize<T>(string? json) =>
        string.IsNullOrWhiteSpace(json) ? default : JsonSerializer.Deserialize<T>(json, Options);
}
