namespace Hanil.TimeGuard.Server.Security;

/// <summary>
/// 관리 화면을 열 수 있는 주소 목록을 들고 있다.
///
/// 설정 파일을 손으로 고치지 않아도 되도록 웹 화면에서 바꿀 수 있게 했고,
/// 바뀌면 곧바로 적용된다.
/// </summary>
public sealed class AdminAccessPolicy
{
    private readonly object _gate = new();

    private AdminNetworkGuard _guard = AdminNetworkGuard.Parse(null, out _);
    private string _configured = string.Empty;

    /// <summary>현재 설정된 주소 문자열.</summary>
    public string Configured
    {
        get { lock (_gate) return _configured; }
    }

    public bool Enabled
    {
        get { lock (_gate) return _guard.Enabled; }
    }

    /// <summary>설정을 바꾼다. 해석하지 못한 항목은 돌려준다.</summary>
    public List<string> Update(string? configured)
    {
        var guard = AdminNetworkGuard.Parse(configured, out var problems);

        lock (_gate)
        {
            _guard = guard;
            _configured = configured?.Trim() ?? string.Empty;
        }

        return problems;
    }

    public bool IsAllowed(System.Net.IPAddress? address)
    {
        lock (_gate) return _guard.IsAllowed(address);
    }
}
