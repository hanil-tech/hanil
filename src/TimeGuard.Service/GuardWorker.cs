using System.Runtime.Versioning;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.State;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Schedule;
using Hanil.TimeGuard.Service.Interop;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Hanil.TimeGuard.Service;

/// <summary>
/// 1초마다 현재 시각을 스케줄과 대조해 경고를 내보내고, 기한이 지나면 설정된 조치를 수행한다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class GuardWorker : BackgroundService
{
    private static readonly TimeSpan TickInterval = TimeSpan.FromSeconds(1);

    /// <summary>조치를 한 번 수행한 뒤 이 시간 동안은 다시 수행하지 않는다(종료가 진행되는 동안의 중복 실행 방지).</summary>
    private static readonly TimeSpan ActionCooldown = TimeSpan.FromMinutes(5);

    /// <summary>에이전트가 떠 있지 않으면 이 간격으로 다시 띄워 본다.</summary>
    private static readonly TimeSpan AgentRelaunchInterval = TimeSpan.FromSeconds(30);

    /// <summary>
    /// 경고를 상태에 얼마나 오래 남겨 둘지.
    /// 에이전트가 1초마다 따로 물어보기 때문에 한 틱만 켜 두면 놓칠 수 있다.
    /// </summary>
    private static readonly TimeSpan NoticeStickyDuration = TimeSpan.FromSeconds(6);

    private readonly ServiceState _state;
    private readonly ILogger<GuardWorker> _logger;
    private readonly string _agentPath;
    private readonly LockedAccountStore _lockedAccounts = new();

    private GuardState? _previousState;
    private DateTimeOffset? _blockedDeadline;
    private bool _countdownCompleted;
    private DateTimeOffset? _lastActionAt;
    private int? _lastNoticeShown;
    private DateTimeOffset? _noticeWindowEnd;
    private DateTimeOffset _lastAgentCheck = DateTimeOffset.MinValue;

    private long _noticeCounter;
    private int? _activeNoticeMinutes;
    private DateTimeOffset _activeNoticeUntil = DateTimeOffset.MinValue;

    private readonly BootAttemptTracker _bootAttempts = new();

    public GuardWorker(ServiceState state, ILogger<GuardWorker> logger)
    {
        _state = state;
        _logger = logger;
        _agentPath = Path.Combine(AppContext.BaseDirectory, "TimeGuard.Agent.exe");
    }

    public override Task StartAsync(CancellationToken cancellationToken)
    {
        _state.Log.Write("서비스", $"서비스를 시작했습니다. 설정 파일: {_state.Store.Path}");
        _state.QueueEvent("서비스", "서비스를 시작했습니다.");

        // 서비스가 멈춰 있는 동안 허용 시간이 되었을 수 있다.
        // 잠긴 계정을 그대로 두면 직원이 출근해도 로그인하지 못하므로 먼저 확인한다.
        var decision = ScheduleEvaluator.Evaluate(_state.Current, DateTimeOffset.Now);
        if (decision.State != GuardState.Blocked)
        {
            ReleaseLockedAccounts("서비스를 시작하며 확인했습니다.");
            ReleaseRemoteAccessBlock();
        }

        return base.StartAsync(cancellationToken);
    }

    public override Task StopAsync(CancellationToken cancellationToken)
    {
        _state.Log.Write("서비스", "서비스를 중지했습니다.");
        _state.QueueEvent("서비스", "서비스를 중지했습니다.");
        return base.StopAsync(cancellationToken);
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                Tick(DateTimeOffset.Now);
            }
            catch (Exception ex)
            {
                // 한 번의 실패로 감시가 멈추면 안 된다.
                _logger.LogError(ex, "감시 루프에서 오류가 발생했습니다.");
                _state.Log.Write("오류", $"감시 루프 오류: {ex.Message}");
            }

            try
            {
                await Task.Delay(TickInterval, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    private void Tick(DateTimeOffset now)
    {
        _state.ReloadIfChanged();

        var config = _state.Current;
        var user = SessionLauncher.GetActiveSessionUser();
        var decision = ScheduleEvaluator.Evaluate(config, now, user);

        EnsureAgentRunning(now, config);

        var snapshot = new StatusSnapshot
        {
            State = decision.State,
            Reason = decision.Reason,
            Enabled = config.Enabled,
            Action = config.Action,
            WindowEnd = decision.WindowEnd,
            NextAllowedStart = decision.NextAllowedStart,
            SuspendedUntil = config.SuspendedUntil,
            ExtensionUntil = config.ExtensionUntil,
            ExtensionApplied = decision.ExtensionApplied,
            Message = config.Warnings.Message,
            ServerTime = now
        };

        switch (decision.State)
        {
            case GuardState.Disabled:
                ResetTracking();
                ReleaseLockedAccounts("제한이 적용되지 않는 상태가 되었습니다.");
                ReleaseRemoteAccessBlock();
                break;

            case GuardState.Allowed:
                // 허용 시간이 되면 잠갔던 계정과 원격 차단을 자동으로 풀어 준다.
                // 이 처리가 없으면 직원이 다음 날에도 로그인하지 못한다.
                ReleaseLockedAccounts("허용 시간이 되었습니다.");
                ReleaseRemoteAccessBlock();
                _bootAttempts.Reset();
                HandleAllowed(config, decision, now, snapshot);
                break;

            case GuardState.Blocked:
                HandleBlocked(config, now, snapshot);
                break;
        }

        _previousState = decision.State;
        _state.PublishStatus(snapshot);
    }

    private void HandleAllowed(GuardConfig config, GuardDecision decision, DateTimeOffset now, StatusSnapshot snapshot)
    {
        _blockedDeadline = null;

        var remaining = decision.Remaining ?? TimeSpan.MaxValue;
        snapshot.RemainingSeconds = remaining.TotalSeconds;

        // 허용 구간이 바뀌면 경고 이력을 초기화한다.
        if (_noticeWindowEnd != decision.WindowEnd)
        {
            _noticeWindowEnd = decision.WindowEnd;
            _lastNoticeShown = null;
            _countdownCompleted = false;
        }

        var notice = ScheduleEvaluator.MatchNoticeMinute(config.Warnings, remaining);
        if (notice is { } minutes && _lastNoticeShown != minutes)
        {
            _lastNoticeShown = minutes;
            RaiseNotice(minutes, now, $"종료 {minutes}분 전 안내를 표시했습니다.");
        }

        ApplyStickyNotice(now, snapshot);

        var countdownSeconds = Math.Max(0, config.Warnings.CountdownSeconds);
        if (remaining <= TimeSpan.FromSeconds(countdownSeconds))
        {
            snapshot.CountdownActive = true;
            snapshot.CountdownSecondsLeft = (int)Math.Ceiling(Math.Max(0, remaining.TotalSeconds));
        }

        // 카운트다운을 끝까지 보여 준 뒤 구간이 끝나면 유예 없이 바로 조치한다.
        if (remaining <= TimeSpan.FromSeconds(2)) _countdownCompleted = true;
    }

    private void HandleBlocked(GuardConfig config, DateTimeOffset now, StatusSnapshot snapshot)
    {
        if (_previousState != GuardState.Blocked || _blockedDeadline is null)
        {
            // 차단 상태로 막 들어왔다.
            // 허용 구간이 정상적으로 끝난 경우라면 이미 경고를 다 했으므로 즉시 조치한다.
            // PC 를 허용 시간 밖에 켠 경우라면 저장할 시간을 주기 위해 유예를 둔다.
            TimeSpan grace;

            if (_countdownCompleted)
            {
                grace = TimeSpan.Zero;
            }
            else
            {
                var baseGrace = TimeSpan.FromSeconds(Math.Max(0, config.Warnings.OutsideWindowGraceSeconds));

                // 껐다 켜기를 되풀이해 유예 시간만큼씩 쓰는 것을 막는다.
                // 같은 차단 구간에서 다시 켤수록 유예가 짧아진다.
                grace = _bootAttempts.NextGrace(baseGrace, now, out var attempt);

                if (attempt > 1)
                {
                    var message = $"허용 시간이 아닌데 {attempt}번째로 켰습니다. 유예를 {grace.TotalSeconds:0}초로 줄였습니다.";

                    _state.Log.Write("차단", message);
                    _state.QueueEvent("차단", message);
                }
            }

            _blockedDeadline = now + grace;
            _lastNoticeShown = null;
            _noticeWindowEnd = null;

            // 원격으로 들어와 쓰는 것도 함께 막는다.
            ApplyRemoteAccessBlock(config);

            _state.Log.Write("차단",
                $"허용 시간대를 벗어났습니다. {grace.TotalSeconds:0}초 뒤 {Describe(config.Action)}을(를) 실행합니다.");

            // 카운트다운 창이 뜨기 전에도 사용자가 알 수 있도록 유예가 길면 먼저 알린다.
            var countdown = TimeSpan.FromSeconds(Math.Max(0, config.Warnings.CountdownSeconds));
            if (grace > countdown)
            {
                var minutesLeft = Math.Max(1, (int)Math.Ceiling(grace.TotalMinutes));
                RaiseNotice(minutesLeft, now, $"허용 시간이 아니어서 {minutesLeft}분 뒤 조치 예정임을 안내했습니다.");
            }
        }

        ApplyStickyNotice(now, snapshot);

        var untilAction = _blockedDeadline.Value - now;
        snapshot.RemainingSeconds = Math.Max(0, untilAction.TotalSeconds);

        var countdownSeconds = Math.Max(0, config.Warnings.CountdownSeconds);
        if (untilAction <= TimeSpan.FromSeconds(countdownSeconds))
        {
            snapshot.CountdownActive = true;
            snapshot.CountdownSecondsLeft = (int)Math.Ceiling(Math.Max(0, untilAction.TotalSeconds));
        }

        if (untilAction > TimeSpan.Zero) return;

        ExecuteAction(config, now, snapshot);
    }

    private void ExecuteAction(GuardConfig config, DateTimeOffset now, StatusSnapshot snapshot)
    {
        if (_lastActionAt is { } last && now - last < ActionCooldown)
        {
            // 이미 조치를 시작했다. 종료가 진행되는 동안 반복 실행하지 않는다.
            snapshot.Warning = "조치를 이미 실행했습니다.";
            return;
        }

        _lastActionAt = now;

        var user = SessionLauncher.GetActiveSessionUser() ?? "(알 수 없음)";
        var start = $"{Describe(config.Action)} 실행을 시작합니다. 사용자: {user}";

        _state.Log.Write("조치", start);
        _state.QueueEvent("조치", start);   // 서버에도 남겨 관리자가 확인할 수 있게 한다

        bool ok;
        string detail;

        if (config.Action == GuardAction.AccountLock)
        {
            // 계정을 잠근 경우에는 나중에 풀어 줄 수 있도록 기록해 둔다.
            string? lockedUser;
            (ok, detail, lockedUser) = PowerController.LockAccountDetailed(config.ExemptUsers);

            if (ok && lockedUser is not null)
                _lockedAccounts.Add(lockedUser, "허용 시간이 끝나 잠갔습니다.");
        }
        else
        {
            (ok, detail) = PowerController.Execute(config.Action);
        }

        _state.Log.Write(ok ? "조치" : "오류", detail);
        _state.QueueEvent(ok ? "조치" : "오류", detail);
        if (!ok)
        {
            _logger.LogError("조치 실행 실패: {Detail}", detail);
            snapshot.Warning = detail;

            // 실패했으면 잠시 뒤 다시 시도할 수 있도록 쿨다운을 짧게 가져간다.
            _lastActionAt = now - ActionCooldown + TimeSpan.FromSeconds(30);
        }
    }

    /// <summary>새 경고를 띄운다. 번호를 올려 에이전트가 이전 경고와 구분할 수 있게 한다.</summary>
    private void RaiseNotice(int minutes, DateTimeOffset now, string logMessage)
    {
        _noticeCounter++;
        _activeNoticeMinutes = minutes;
        _activeNoticeUntil = now + NoticeStickyDuration;

        _state.Log.Write("경고", logMessage);
    }

    /// <summary>아직 유효한 경고가 있으면 상태에 실어 보낸다.</summary>
    private void ApplyStickyNotice(DateTimeOffset now, StatusSnapshot snapshot)
    {
        if (_activeNoticeMinutes is not { } minutes || now >= _activeNoticeUntil) return;

        snapshot.NoticeMinutes = minutes;
        snapshot.NoticeId = _noticeCounter;
    }

    /// <summary>
    /// 잠가 둔 계정을 모두 풀어 준다.
    /// 허용 시간이 되었거나 제한이 꺼졌을 때 호출한다.
    /// </summary>
    private void ReleaseLockedAccounts(string why)
    {
        var locked = _lockedAccounts.Load();
        if (locked.Count == 0) return;

        foreach (var entry in locked)
        {
            var (ok, detail) = PowerController.UnlockAccount(entry.UserName);

            if (ok)
            {
                _lockedAccounts.Remove(entry.UserName);

                _state.Log.Write("조치", $"{detail} ({why})");
                _state.QueueEvent("조치", $"{entry.UserName} 계정 잠금을 풀었습니다. {why}");
            }
            else
            {
                _logger.LogError("계정 잠금을 풀지 못했습니다: {Detail}", detail);
                _state.Log.Write("오류", $"계정 잠금을 풀지 못했습니다: {detail}");
            }
        }
    }

    /// <summary>설정이 켜져 있으면 원격 접속을 막는다.</summary>
    private void ApplyRemoteAccessBlock(GuardConfig config)
    {
        if (!config.BlockRemoteAccess) return;
        if (RemoteAccessController.IsBlockedByUs()) return;

        var (ok, detail) = RemoteAccessController.Block();

        if (ok)
        {
            if (string.IsNullOrEmpty(detail)) return;

            _state.Log.Write("차단", detail);
            _state.QueueEvent("차단", detail);
        }
        else
        {
            _logger.LogError("원격 접속을 막지 못했습니다: {Detail}", detail);
            _state.Log.Write("오류", detail);
        }
    }

    /// <summary>우리가 막아 둔 원격 접속 차단을 푼다.</summary>
    private void ReleaseRemoteAccessBlock()
    {
        if (!RemoteAccessController.IsBlockedByUs()) return;

        var (ok, detail) = RemoteAccessController.Unblock();

        if (ok)
        {
            if (string.IsNullOrEmpty(detail)) return;

            _state.Log.Write("조치", detail);
            _state.QueueEvent("조치", detail);
        }
        else
        {
            _logger.LogError("원격 접속 차단을 풀지 못했습니다: {Detail}", detail);
            _state.Log.Write("오류", detail);
        }
    }

    private void ResetTracking()
    {
        _blockedDeadline = null;
        _countdownCompleted = false;
        _lastNoticeShown = null;
        _noticeWindowEnd = null;
        _activeNoticeMinutes = null;
        _activeNoticeUntil = DateTimeOffset.MinValue;
    }

    /// <summary>
    /// 사용자가 에이전트를 종료해도 경고가 다시 뜨도록 주기적으로 다시 띄운다.
    /// 에이전트가 없어도 조치 자체는 서비스가 수행하므로 차단을 피할 수는 없다.
    /// </summary>
    private void EnsureAgentRunning(DateTimeOffset now, GuardConfig config)
    {
        if (now - _lastAgentCheck < AgentRelaunchInterval) return;
        _lastAgentCheck = now;

        if (!config.Enabled) return;
        if (!File.Exists(_agentPath)) return;

        try
        {
            var sessionId = SessionLauncher.FindActiveSessionId();
            if (sessionId is null) return;

            var running = false;
            foreach (var process in System.Diagnostics.Process.GetProcessesByName("TimeGuard.Agent"))
            {
                using (process)
                {
                    try
                    {
                        if (process.SessionId == sessionId.Value) running = true;
                    }
                    catch
                    {
                        // 접근할 수 없는 프로세스는 건너뛴다.
                    }
                }
            }

            if (running) return;

            if (SessionLauncher.LaunchInSession(sessionId.Value, $"\"{_agentPath}\"", showWindow: false, out var error))
                _state.Log.Write("에이전트", $"세션 {sessionId} 에 알림 프로그램을 실행했습니다.");
            else
                _logger.LogWarning("알림 프로그램을 실행하지 못했습니다: {Error}", error);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "알림 프로그램 상태를 확인하지 못했습니다.");
        }
    }

    internal static string Describe(GuardAction action) => action switch
    {
        GuardAction.Shutdown => "전원 차단",
        GuardAction.LogOff => "로그오프",
        GuardAction.Lock => "화면 잠금",
        GuardAction.AccountLock => "계정 잠금",
        _ => action.ToString()
    };
}
