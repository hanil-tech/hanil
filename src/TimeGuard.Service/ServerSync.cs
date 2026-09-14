using System.Runtime.Versioning;
using Hanil.TimeGuard.Core;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Service.Interop;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Hanil.TimeGuard.Service;

/// <summary>
/// 관리 서버와 주기적으로 연락해 정책을 받아 오고, 기록과 요청을 올린다.
///
/// 서버에 닿지 못해도 마지막으로 받은 정책이 그대로 적용되므로,
/// 랜선을 뽑거나 서버를 꺼서 제한을 피할 수는 없다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class ServerSync : BackgroundService
{
    /// <summary>연락이 끊겼을 때 다시 시도하는 간격.</summary>
    private static readonly TimeSpan RetryInterval = TimeSpan.FromSeconds(30);

    /// <summary>한 번에 올리는 기록 개수.</summary>
    private const int EventBatchSize = 50;

    private readonly ServiceState _state;
    private readonly ILogger<ServerSync> _logger;

    private ServerSettings _settings = new();
    private ServerConnection? _connection;
    private PolicyCache _cache = new();

    private bool _lastReachable = true;
    private DateTimeOffset _lastFailureLogged = DateTimeOffset.MinValue;

    public ServerSync(ServiceState state, ILogger<ServerSync> logger)
    {
        _state = state;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _settings = ServerSettings.Load();

        if (!_settings.IsConfigured)
        {
            _logger.LogInformation("관리 서버가 설정되어 있지 않아 단독 모드로 동작합니다.");
            _state.SetServerMode(false, null);
            return;
        }

        _state.SetServerMode(true, _settings.ServerUrl);
        _connection = new ServerConnection(_settings);

        // 서버가 아직 응답하지 않더라도, 보관된 정책이 있으면 바로 적용한다.
        ApplyCachedPolicyAtStartup();

        _logger.LogInformation("관리 서버를 사용합니다: {Url}", _settings.ServerUrl);
        _state.Log.Write("서버", $"관리 서버에 연결을 시작합니다: {_settings.ServerUrl}");

        while (!stoppingToken.IsCancellationRequested)
        {
            var interval = TimeSpan.FromSeconds(Math.Clamp(_settings.PollSeconds, 10, 3600));

            try
            {
                await SyncOnceAsync(stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                // 서버 통신 실패가 감시 자체를 멈추게 해서는 안 된다.
                _logger.LogError(ex, "서버와 동기화하는 중 오류가 발생했습니다.");
            }

            try
            {
                await Task.Delay(_lastReachable ? interval : RetryInterval, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    /// <summary>
    /// 서비스가 막 떴을 때, 서버에 닿기 전이라도 보관된 정책을 적용한다.
    /// 이 처리가 없으면 PC 를 껐다 켜는 것만으로 잠시 제한이 풀린다.
    /// </summary>
    private void ApplyCachedPolicyAtStartup()
    {
        var cached = _cache.Load();
        if (cached is null)
        {
            _logger.LogWarning("보관된 정책이 없습니다. 서버에서 정책을 받을 때까지 제한이 적용되지 않습니다.");
            return;
        }

        _state.ApplyServerPolicy(cached.Policy, cached.Stamp, fromCache: true);

        _logger.LogInformation("보관된 정책을 적용했습니다. 받은 시각: {ReceivedAt}", cached.ReceivedAt);
        _state.Log.Write("서버", $"서버에 연결되기 전까지 마지막으로 받은 시간표를 적용합니다({cached.ReceivedAt:yyyy-MM-dd HH:mm} 수신).");
    }

    private async Task SyncOnceAsync(CancellationToken token)
    {
        if (_connection is null) return;

        var status = _state.Status;
        var machineName = Environment.MachineName;
        var osUser = SessionLauncher.GetActiveSessionUser() ?? string.Empty;

        // 아직 등록되지 않았으면 먼저 등록한다.
        if (!_settings.IsEnrolled)
        {
            if (string.IsNullOrWhiteSpace(_settings.EnrollmentKey))
            {
                LogFailureOccasionally("등록 키가 없어 서버에 등록할 수 없습니다. 설치 시 등록 키를 입력해 주세요.");
                return;
            }

            var (ok, message) = await _connection.EnrollAsync(machineName, osUser, _settings.EnrollmentKey, token);

            if (!ok)
            {
                LogFailureOccasionally($"서버 등록에 실패했습니다: {message}");
                _lastReachable = false;
                return;
            }

            _logger.LogInformation("서버에 등록했습니다: {Message}", message);
            _state.Log.Write("서버", message);
        }

        var heartbeat = new HeartbeatRequest
        {
            PolicyStamp = _state.PolicyStamp,
            State = status.State.ToString(),
            Reason = status.Reason,
            OsUser = osUser,
            RemainingSeconds = status.RemainingSeconds,
            ClientVersion = typeof(ServerSync).Assembly.GetName().Version?.ToString() ?? "1.0.0"
        };

        var result = await _connection.SyncAsync(heartbeat, machineName, token);

        if (!result.Reached)
        {
            if (_lastReachable)
            {
                _logger.LogWarning("서버와 연락이 끊겼습니다: {Error}", result.Error);
                _state.Log.Write("서버", $"서버와 연락이 끊겼습니다. 마지막으로 받은 시간표를 계속 적용합니다. ({result.Error})");
            }

            _lastReachable = false;
            _state.SetServerReachable(false);
            return;
        }

        if (!_lastReachable)
        {
            _logger.LogInformation("서버와 다시 연결되었습니다.");
            _state.Log.Write("서버", "서버와 다시 연결되었습니다.");
        }

        _lastReachable = true;
        _state.SetServerReachable(true);

        // 정책이 바뀌었으면 저장하고 적용한다.
        if (result.NewPolicy is not null && result.PolicyStamp is not null)
        {
            _cache.Save(result.NewPolicy, result.PolicyStamp);
            _state.ApplyServerPolicy(result.NewPolicy, result.PolicyStamp, fromCache: false);

            _logger.LogInformation("서버에서 새 정책을 받았습니다. 표식: {Stamp}", result.PolicyStamp);
            _state.Log.Write("서버", "서버에서 새 시간표를 받아 적용했습니다.");
        }
        else if (result.PolicyStamp is not null)
        {
            _state.UpdatePolicyStamp(result.PolicyStamp);
        }

        // 연장과 일시 중지는 자주 바뀌므로 매번 반영한다.
        _state.ApplyServerOverrides(result.ExtensionUntil, result.SuspendedUntil);

        // 사용자에게 알릴 처리 결과를 서비스 상태에 실어 둔다. 에이전트가 가져가 보여 준다.
        foreach (var decision in result.Decisions)
        {
            _state.QueueDecision(decision);

            var summary = decision.Status == "Approved"
                ? $"연장 요청이 승인되었습니다. {decision.GrantedMinutes}분 ({decision.GrantedUntil:HH:mm} 까지)"
                : $"연장 요청이 거절되었습니다." + (string.IsNullOrWhiteSpace(decision.Note) ? "" : $" 사유: {decision.Note}");

            _state.Log.Write("서버", summary);
        }

        await UploadPendingEventsAsync(token);
    }

    /// <summary>서비스가 남긴 기록 중 아직 올리지 않은 것을 서버로 보낸다.</summary>
    private async Task UploadPendingEventsAsync(CancellationToken token)
    {
        if (_connection is null) return;

        var pending = _state.TakePendingEvents(EventBatchSize);
        if (pending.Count == 0) return;

        var uploaded = await _connection.ReportEventsAsync(pending, token);

        if (!uploaded)
        {
            // 실패하면 다시 넣어 두어 다음 기회에 올린다.
            _state.RestorePendingEvents(pending);
        }
    }

    /// <summary>같은 실패를 매번 기록해 로그를 채우지 않도록 한다.</summary>
    private void LogFailureOccasionally(string message)
    {
        var now = DateTimeOffset.Now;
        if (now - _lastFailureLogged < TimeSpan.FromMinutes(10)) return;

        _lastFailureLogged = now;
        _logger.LogWarning("{Message}", message);
        _state.Log.Write("서버", message);
    }

    public override void Dispose()
    {
        _connection?.Dispose();
        base.Dispose();
    }
}
