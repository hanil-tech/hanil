using Hanil.TimeGuard.Core;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;

namespace Hanil.TimeGuard.Service;

/// <summary>
/// 감시 루프와 IPC 서버가 함께 쓰는 상태.
/// 설정은 항상 이 클래스를 통해서만 읽고 쓴다.
/// </summary>
public sealed class ServiceState
{
    private readonly object _gate = new();
    private GuardConfig _config;
    private DateTime _configWriteTimeUtc;
    private StatusSnapshot _snapshot = new();

    // --- 서버 모드 ---
    private bool _serverMode;
    private string? _serverUrl;
    private bool _serverReachable;
    private string? _policyStamp;
    private readonly Queue<EventEntry> _pendingEvents = new();
    private readonly Queue<RequestDecision> _pendingDecisions = new();

    /// <summary>서버로 보내지 못한 기록을 무한정 쌓지 않도록 제한한다.</summary>
    private const int MaxPendingEvents = 500;

    public ConfigStore Store { get; }
    public AuditLog Log { get; }

    public ServiceState(ConfigStore store, AuditLog log)
    {
        Store = store;
        Log = log;
        _config = store.Load(out var error);
        _configWriteTimeUtc = CurrentWriteTimeUtc();

        if (error is not null) Log.Write("설정", error);
    }

    // ================= 서버 모드 =================

    /// <summary>관리 서버가 설정되어 있는지. 이 경우 설정은 서버만 바꿀 수 있다.</summary>
    public bool ServerMode
    {
        get { lock (_gate) return _serverMode; }
    }

    public string? ServerUrl
    {
        get { lock (_gate) return _serverUrl; }
    }

    public bool ServerReachable
    {
        get { lock (_gate) return _serverReachable; }
    }

    /// <summary>현재 적용 중인 정책의 표식. 서버에 바뀐 게 있는지 물어볼 때 쓴다.</summary>
    public string? PolicyStamp
    {
        get { lock (_gate) return _policyStamp; }
    }

    public void SetServerMode(bool enabled, string? url)
    {
        lock (_gate)
        {
            _serverMode = enabled;
            _serverUrl = url;
        }
    }

    public void SetServerReachable(bool reachable)
    {
        lock (_gate) _serverReachable = reachable;
    }

    public void UpdatePolicyStamp(string stamp)
    {
        lock (_gate) _policyStamp = stamp;
    }

    /// <summary>
    /// 서버에서 받은 정책을 적용한다.
    /// 서버가 관리하는 항목만 덮어쓰고, 이 PC 고유의 값(비밀번호 등)은 건드리지 않는다.
    /// </summary>
    public void ApplyServerPolicy(GuardConfig policy, string stamp, bool fromCache)
    {
        ArgumentNullException.ThrowIfNull(policy);

        lock (_gate)
        {
            _config.Enabled = policy.Enabled;
            _config.Action = policy.Action;
            _config.Schedule = policy.Schedule ?? _config.Schedule;
            _config.Warnings = policy.Warnings ?? _config.Warnings;
            _config.Holidays = policy.Holidays ?? _config.Holidays;
            _config.HolidayPolicy = policy.HolidayPolicy;
            _config.ExemptUsers = policy.ExemptUsers ?? _config.ExemptUsers;
            _config.ExtensionUntil = policy.ExtensionUntil;
            _config.SuspendedUntil = policy.SuspendedUntil;

            _policyStamp = stamp;
            _serverMode = true;

            // 서버 정책도 파일에 남겨 둔다. 다음 기동 때 바로 쓸 수 있고 관리자가 확인하기도 좋다.
            try
            {
                Store.Save(_config, fromCache ? "서버(보관본)" : "서버");
                _configWriteTimeUtc = CurrentWriteTimeUtc();
            }
            catch (Exception ex)
            {
                Log.Write("오류", $"서버 정책을 파일에 저장하지 못했습니다: {ex.Message}");
            }
        }
    }

    /// <summary>연장과 일시 중지만 갱신한다. 매번 바뀔 수 있어 정책과 분리해 둔다.</summary>
    public void ApplyServerOverrides(DateTimeOffset? extensionUntil, DateTimeOffset? suspendedUntil)
    {
        lock (_gate)
        {
            if (_config.ExtensionUntil == extensionUntil && _config.SuspendedUntil == suspendedUntil)
                return;

            _config.ExtensionUntil = extensionUntil;
            _config.SuspendedUntil = suspendedUntil;

            try
            {
                Store.Save(_config, "서버");
                _configWriteTimeUtc = CurrentWriteTimeUtc();
            }
            catch (Exception ex)
            {
                Log.Write("오류", $"연장 정보를 저장하지 못했습니다: {ex.Message}");
            }
        }
    }

    /// <summary>서버로 올릴 기록을 쌓아 둔다.</summary>
    public void QueueEvent(string category, string message)
    {
        lock (_gate)
        {
            if (!_serverMode) return;

            if (_pendingEvents.Count >= MaxPendingEvents) _pendingEvents.Dequeue();

            _pendingEvents.Enqueue(new EventEntry
            {
                At = DateTimeOffset.Now,
                Category = category,
                Message = message
            });
        }
    }

    public List<EventEntry> TakePendingEvents(int max)
    {
        lock (_gate)
        {
            var taken = new List<EventEntry>();

            while (taken.Count < max && _pendingEvents.Count > 0)
                taken.Add(_pendingEvents.Dequeue());

            return taken;
        }
    }

    /// <summary>올리지 못한 기록을 되돌려 놓는다. 순서를 지키기 위해 앞쪽에 다시 넣는다.</summary>
    public void RestorePendingEvents(List<EventEntry> entries)
    {
        lock (_gate)
        {
            var rest = _pendingEvents.ToList();
            _pendingEvents.Clear();

            foreach (var entry in entries) _pendingEvents.Enqueue(entry);
            foreach (var entry in rest) _pendingEvents.Enqueue(entry);

            while (_pendingEvents.Count > MaxPendingEvents) _pendingEvents.Dequeue();
        }
    }

    /// <summary>사용자에게 알릴 연장 요청 처리 결과를 쌓아 둔다.</summary>
    public void QueueDecision(RequestDecision decision)
    {
        lock (_gate)
        {
            if (_pendingDecisions.Count >= 10) _pendingDecisions.Dequeue();
            _pendingDecisions.Enqueue(decision);
        }
    }

    /// <summary>쌓인 처리 결과를 하나 꺼낸다. 없으면 null.</summary>
    public RequestDecision? DequeueDecision()
    {
        lock (_gate) return _pendingDecisions.Count > 0 ? _pendingDecisions.Dequeue() : null;
    }

    /// <summary>현재 설정의 사본을 돌려준다. 호출자가 고쳐도 서비스 상태에 영향이 없다.</summary>
    public GuardConfig Snapshot()
    {
        lock (_gate)
        {
            var json = System.Text.Json.JsonSerializer.Serialize(_config);
            return System.Text.Json.JsonSerializer.Deserialize<GuardConfig>(json)!;
        }
    }

    /// <summary>감시 루프가 매 초 읽는 설정. 사본을 만들지 않아 가볍다.</summary>
    public GuardConfig Current
    {
        get { lock (_gate) return _config; }
    }

    /// <summary>
    /// 설정 파일이 밖에서 바뀌었으면 다시 읽는다.
    /// 서버 모드에서는 파일을 고쳐 제한을 푸는 것을 막기 위해, 서버가 준 정책을 파일에 되쓴다.
    /// </summary>
    public bool ReloadIfChanged()
    {
        lock (_gate)
        {
            var writeTime = CurrentWriteTimeUtc();
            if (writeTime == _configWriteTimeUtc) return false;

            if (_serverMode)
            {
                Log.Write("설정", "설정 파일이 밖에서 바뀌었지만 서버 정책이 우선이므로 되돌립니다.");

                try
                {
                    Store.Save(_config, "서버");
                    _configWriteTimeUtc = CurrentWriteTimeUtc();
                }
                catch (Exception ex)
                {
                    Log.Write("오류", $"설정 파일을 되돌리지 못했습니다: {ex.Message}");
                    _configWriteTimeUtc = writeTime;
                }

                return false;
            }

            var reloaded = Store.Load(out var error);
            if (error is not null) Log.Write("설정", error);

            _config = reloaded;
            _configWriteTimeUtc = writeTime;
            Log.Write("설정", "설정 파일이 변경되어 다시 읽었습니다.");
            return true;
        }
    }

    /// <summary>설정을 바꾸고 파일에 저장한다.</summary>
    public void Update(Action<GuardConfig> change, string modifiedBy, string description)
    {
        lock (_gate)
        {
            change(_config);
            Store.Save(_config, modifiedBy);
            _configWriteTimeUtc = CurrentWriteTimeUtc();
            Log.Write("설정", $"{description} (변경자: {modifiedBy})");
        }
    }

    public StatusSnapshot Status
    {
        get { lock (_gate) return _snapshot; }
    }

    public void PublishStatus(StatusSnapshot snapshot)
    {
        lock (_gate) _snapshot = snapshot;
    }

    /// <summary>관리자 비밀번호를 확인한다. 비밀번호가 설정돼 있지 않으면 최초 설정으로 간주해 통과시킨다.</summary>
    public bool Authenticate(string? password, out string error)
    {
        lock (_gate)
        {
            if (string.IsNullOrEmpty(_config.PasswordHash))
            {
                error = string.Empty;
                return true; // 최초 설정 상태
            }

            if (PasswordHasher.Verify(password ?? string.Empty, _config.PasswordHash))
            {
                error = string.Empty;
                return true;
            }

            error = "관리자 비밀번호가 올바르지 않습니다.";
            return false;
        }
    }

    public bool PasswordIsSet
    {
        get { lock (_gate) return !string.IsNullOrEmpty(_config.PasswordHash); }
    }

    private DateTime CurrentWriteTimeUtc()
    {
        try
        {
            var info = new FileInfo(Store.Path);
            return info.Exists ? info.LastWriteTimeUtc : DateTime.MinValue;
        }
        catch
        {
            return DateTime.MinValue;
        }
    }
}
