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

    /// <summary>설치 직후 서버를 찾는 간격. 빨리 붙어야 관리자가 바로 승인할 수 있다.</summary>
    private static readonly TimeSpan FirstSearchInterval = TimeSpan.FromSeconds(10);

    /// <summary>한참 못 찾았을 때의 간격. 사내망에 신호를 계속 뿌리지 않도록 늦춘다.</summary>
    private static readonly TimeSpan SlowSearchInterval = TimeSpan.FromMinutes(2);

    /// <summary>빠른 간격으로 찾아 보는 횟수. 약 2분.</summary>
    private const int FastSearchAttempts = 12;

    /// <summary>이만큼 연락이 끊겨 있으면 서버가 옮겨 갔는지 다시 찾아본다.</summary>
    private static readonly TimeSpan RediscoverAfter = TimeSpan.FromMinutes(10);

    /// <summary>한 번에 올리는 기록 개수.</summary>
    private const int EventBatchSize = 50;

    private readonly ServiceState _state;
    private readonly ILogger<ServerSync> _logger;

    private ServerSettings _settings = new();
    private ServerConnection? _connection;
    private PolicyCache _cache = new();

    private bool _lastReachable = true;
    private DateTimeOffset _lastFailureLogged = DateTimeOffset.MinValue;

    /// <summary>연락이 끊긴 시각. 오래되면 서버를 다시 찾아본다.</summary>
    private DateTimeOffset? _unreachableSince;

    /// <summary>승인 대기 안내를 한 번만 남기기 위한 표시.</summary>
    private bool _waitingLogged;

    public ServerSync(ServiceState state, ILogger<ServerSync> logger)
    {
        _state = state;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _settings = ServerSettings.Load();

        // 설치 직후에는 서버 주소를 모른다. 사내망에서 찾아낼 때까지 기다린다.
        // 관리자가 일부러 단독 모드로 둔 경우에만 찾지 않는다.
        if (_settings.ShouldDiscoverServer)
        {
            _state.SetServerMode(false, null);
            _state.Log.Write("서버", "사내망에서 관리 서버를 찾는 중입니다.");

            if (!await SearchUntilFoundAsync(stoppingToken)) return;
        }

        if (!_settings.IsConfigured)
        {
            _logger.LogInformation("관리 서버 없이 단독 모드로 동작합니다.");
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
            // 승인을 기다리는 동안에는 자주 확인한다. 관리자가 승인하면 바로 동작해야 한다.
            var interval = _settings.IsEnrolled
                ? TimeSpan.FromSeconds(Math.Clamp(_settings.PollSeconds, 10, 3600))
                : TimeSpan.FromSeconds(10);

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
    /// 사내망에서 관리 서버를 찾을 때까지 되풀이한다.
    ///
    /// 설치할 때 서버 주소를 적어 넣지 않아도 되게 하는 부분이다.
    /// 서버가 아직 안 켜져 있거나 나중에 설치될 수도 있으므로 계속 찾는다.
    /// 서비스가 멈출 때만 false 를 돌려준다.
    /// </summary>
    private async Task<bool> SearchUntilFoundAsync(CancellationToken token)
    {
        var attempts = 0;

        while (!token.IsCancellationRequested)
        {
            var found = await FindOneAsync(token);

            if (found is not null)
            {
                _settings.ServerUrl = found.Url.TrimEnd('/');
                _settings.ServerMachineName = found.MachineName;
                _settings.StandaloneMode = false;
                _settings.Save();

                _logger.LogInformation("관리 서버를 찾았습니다: {Url} ({Machine})", found.Url, found.MachineName);
                _state.Log.Write("서버", $"관리 서버를 찾았습니다: {found.Url} ({found.MachineName})");

                return true;
            }

            attempts++;

            if (attempts == FastSearchAttempts)
            {
                _logger.LogWarning("사내망에서 관리 서버를 찾지 못했습니다. 계속 찾습니다.");
                _state.Log.Write("서버",
                    "사내망에서 관리 서버를 찾지 못했습니다. 서버가 켜져 있는지, " +
                    "서버 방화벽에서 UDP 8765 가 열려 있는지 확인해 주세요. 계속 찾습니다.");
            }

            var wait = attempts < FastSearchAttempts ? FirstSearchInterval : SlowSearchInterval;

            try
            {
                await Task.Delay(wait, token);
            }
            catch (OperationCanceledException)
            {
                return false;
            }
        }

        return false;
    }

    /// <summary>사내망에 한 번 물어보고 쓸 만한 서버 하나를 고른다.</summary>
    private async Task<DiscoveredServer?> FindOneAsync(CancellationToken token)
    {
        List<DiscoveredServer> servers;

        try
        {
            servers = await ServerDiscovery.FindAsync(token: token);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogDebug(ex, "서버를 찾는 중 문제가 있었습니다.");
            return null;
        }

        if (servers.Count == 0) return null;

        if (servers.Count > 1)
        {
            _logger.LogWarning("관리 서버가 여러 대 응답했습니다: {Servers}",
                string.Join(", ", servers.Select(s => s.ToString())));
        }

        return servers[0];
    }

    /// <summary>
    /// 서버가 다른 주소로 옮겨 갔는지 찾아본다.
    ///
    /// 사내망은 대개 주소를 자동으로 나눠 주기 때문에 서버 PC 의 주소가 바뀔 수 있다.
    /// 그대로 두면 옛 주소만 붙잡고 영영 연결되지 않는다.
    ///
    /// 다만 아무 서버에나 붙으면 안 된다. 처음에 붙었던 서버 PC 이름이 같을 때만 옮긴다.
    /// 기억해 둔 인증서 지문은 그대로 두므로, 이름을 흉내 낸 가짜 서버에는 연결되지 않는다.
    /// </summary>
    private async Task TryRediscoverAsync(CancellationToken token)
    {
        if (string.IsNullOrWhiteSpace(_settings.ServerMachineName)) return;

        var found = await FindOneAsync(token);
        if (found is null) return;

        var sameUrl = string.Equals(found.Url.TrimEnd('/'), _settings.ServerUrl, StringComparison.OrdinalIgnoreCase);
        if (sameUrl) return;

        if (!string.Equals(found.MachineName, _settings.ServerMachineName, StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("다른 이름의 서버가 응답했습니다. 옮기지 않습니다: {Machine}", found.MachineName);
            return;
        }

        var previous = _settings.ServerUrl;

        _settings.ServerUrl = found.Url.TrimEnd('/');
        _settings.Save();

        _connection?.Dispose();
        _connection = new ServerConnection(_settings);

        _state.SetServerMode(true, _settings.ServerUrl);
        _unreachableSince = null;

        _logger.LogInformation("서버 주소가 바뀐 것을 확인했습니다: {Old} -> {New}", previous, _settings.ServerUrl);
        _state.Log.Write("서버", $"관리 서버 주소가 바뀌어 다시 연결합니다: {previous} -> {_settings.ServerUrl}");
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
            if (!await RegisterAsync(machineName, osUser, token)) return;
        }

        var heartbeat = new HeartbeatRequest
        {
            PolicyStamp = _state.PolicyStamp,
            State = status.State.ToString(),
            Reason = status.Reason,
            OsUser = osUser,
            RemainingSeconds = status.RemainingSeconds,
            ClientVersion = typeof(ServerSync).Assembly.GetName().Version?.ToString() ?? "1.0.0",
            UserIsAdministrator = DescribeAdminRights(osUser)
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

            _unreachableSince ??= DateTimeOffset.Now;

            // 오래 끊겨 있으면 서버가 다른 주소로 옮겨 갔는지 확인한다.
            if (DateTimeOffset.Now - _unreachableSince.Value >= RediscoverAfter)
            {
                _unreachableSince = DateTimeOffset.Now;
                await TryRediscoverAsync(token);
            }

            return;
        }

        if (!_lastReachable)
        {
            _logger.LogInformation("서버와 다시 연결되었습니다.");
            _state.Log.Write("서버", "서버와 다시 연결되었습니다.");
        }

        _lastReachable = true;
        _unreachableSince = null;
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

    /// <summary>
    /// 이 PC 를 서버에 등록한다.
    ///
    /// 등록 키가 있으면 곧바로 등록한다(여러 대를 한꺼번에 설치할 때).
    /// 없으면 서버에 자기를 알리고 관리자가 승인할 때까지 기다린다.
    /// 승인되면 다음 연락에서 자동으로 토큰을 받아 간다.
    /// </summary>
    private async Task<bool> RegisterAsync(string machineName, string osUser, CancellationToken token)
    {
        if (_connection is null) return false;

        if (!string.IsNullOrWhiteSpace(_settings.EnrollmentKey))
        {
            var (ok, message) = await _connection.EnrollAsync(machineName, osUser, _settings.EnrollmentKey, token);

            if (!ok)
            {
                LogFailureOccasionally($"서버 등록에 실패했습니다: {message}");
                _lastReachable = false;
                return false;
            }

            _logger.LogInformation("서버에 등록했습니다: {Message}", message);
            _state.Log.Write("서버", message);
            return true;
        }

        // 승인 방식. 먼저 자기를 알린다.
        var (reached, state, announceMessage) = await _connection.AnnounceAsync(machineName, osUser, token);

        if (!reached)
        {
            LogFailureOccasionally($"서버에 알리지 못했습니다: {announceMessage}");
            _lastReachable = false;
            return false;
        }

        _lastReachable = true;

        if (state == ApprovalStates.Rejected)
        {
            LogFailureOccasionally("관리자가 이 PC 의 등록을 거절했습니다. 관리자에게 문의해 주세요.");
            _state.SetApprovalState(state);
            return false;
        }

        // 승인되었는지 확인하고, 되었으면 토큰을 받아 온다.
        var (approved, claimState, claimMessage) = await _connection.ClaimAsync(machineName, token);

        _state.SetApprovalState(claimState);

        if (!approved)
        {
            // 승인을 기다리는 것은 정상 상태다. 매번 기록하지 않는다.
            if (!_waitingLogged)
            {
                _waitingLogged = true;
                _logger.LogInformation("서버에 등록을 요청했습니다. 관리자 승인을 기다립니다.");
                _state.Log.Write("서버",
                    "서버에 이 PC 를 알렸습니다. 관리자가 승인하면 시간표를 받아 옵니다. " +
                    $"확인 문자: {ServerSettings.DescribeFingerprint(_settings.ClientId)}");
            }

            return false;
        }

        _waitingLogged = false;

        _logger.LogInformation("승인되어 등록을 마쳤습니다: {Message}", claimMessage);
        _state.Log.Write("서버", claimMessage);
        _state.QueueEvent("서버", "관리자 승인 후 등록을 마쳤습니다.");

        return true;
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

    /// <summary>
    /// 로그인한 계정이 이 PC 의 관리자인지 확인한다.
    /// 확인하지 못하면 null 을 돌려준다. 잘못된 정보를 올리는 것보다 낫다.
    /// </summary>
    private static bool? DescribeAdminRights(string osUser)
    {
        if (string.IsNullOrWhiteSpace(osUser)) return null;

        try
        {
            return AccountController.IsAdministrator(osUser);
        }
        catch (Exception)
        {
            return null;
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
