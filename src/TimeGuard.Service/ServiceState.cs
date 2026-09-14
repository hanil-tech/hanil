using Hanil.TimeGuard.Core;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;

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

    /// <summary>설정 파일이 밖에서 바뀌었으면 다시 읽는다.</summary>
    public bool ReloadIfChanged()
    {
        lock (_gate)
        {
            var writeTime = CurrentWriteTimeUtc();
            if (writeTime == _configWriteTimeUtc) return false;

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
