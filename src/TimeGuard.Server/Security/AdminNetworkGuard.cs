using System.Net;
using System.Net.Sockets;

namespace Hanil.TimeGuard.Server.Security;

/// <summary>
/// 관리 화면을 볼 수 있는 위치를 제한한다.
///
/// 직원 PC 는 클라이언트 API(/api/...) 만 쓰면 되고 관리 화면은 볼 이유가 없다.
/// 관리자 PC 주소만 등록해 두면, 직원 PC 에서는 로그인 화면조차 열리지 않는다.
/// 비밀번호를 알아내도 접속할 곳이 없어진다.
/// </summary>
public sealed class AdminNetworkGuard
{
    private readonly List<Rule> _rules = new();

    public bool Enabled => _rules.Count > 0;

    /// <summary>설정 문자열을 해석한다. 예: "192.168.0.5, 192.168.10.0/24".</summary>
    public static AdminNetworkGuard Parse(string? configured, out List<string> problems)
    {
        var guard = new AdminNetworkGuard();
        problems = new List<string>();

        if (string.IsNullOrWhiteSpace(configured)) return guard;

        foreach (var raw in configured.Split(new[] { ',', ';', '\n', '\r' },
                     StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (TryParseRule(raw, out var rule)) guard._rules.Add(rule);
            else problems.Add(raw);
        }

        return guard;
    }

    /// <summary>이 주소에서 관리 화면을 열 수 있는지.</summary>
    public bool IsAllowed(IPAddress? address)
    {
        // 제한을 걸지 않았으면 모두 허용한다(기본값).
        if (_rules.Count == 0) return true;

        if (address is null) return false;

        // 서버 PC 자신은 언제나 허용한다.
        // 이렇게 해 두지 않으면 설정을 잘못 넣었을 때 아무도 못 들어가 손쓸 수 없다.
        if (IPAddress.IsLoopback(address)) return true;

        var candidate = Normalize(address);

        foreach (var rule in _rules)
        {
            if (rule.Matches(candidate)) return true;
        }

        return false;
    }

    /// <summary>IPv6 로 감싸인 IPv4 주소를 원래 형태로 되돌린다.</summary>
    private static IPAddress Normalize(IPAddress address) =>
        address.IsIPv4MappedToIPv6 ? address.MapToIPv4() : address;

    private static bool TryParseRule(string text, out Rule rule)
    {
        rule = default!;

        var slash = text.IndexOf('/');

        if (slash < 0)
        {
            if (!IPAddress.TryParse(text, out var single)) return false;
            rule = new Rule(Normalize(single), null);
            return true;
        }

        var addressPart = text[..slash];
        var prefixPart = text[(slash + 1)..];

        if (!IPAddress.TryParse(addressPart, out var network)) return false;
        if (!int.TryParse(prefixPart, out var prefix)) return false;

        network = Normalize(network);

        var maxPrefix = network.AddressFamily == AddressFamily.InterNetwork ? 32 : 128;
        if (prefix < 0 || prefix > maxPrefix) return false;

        rule = new Rule(network, prefix);
        return true;
    }

    private readonly record struct Rule(IPAddress Network, int? Prefix)
    {
        public bool Matches(IPAddress candidate)
        {
            if (candidate.AddressFamily != Network.AddressFamily) return false;

            var networkBytes = Network.GetAddressBytes();
            var candidateBytes = candidate.GetAddressBytes();

            if (Prefix is not { } prefix)
                return networkBytes.AsSpan().SequenceEqual(candidateBytes);

            var fullBytes = prefix / 8;
            var remainingBits = prefix % 8;

            for (var i = 0; i < fullBytes; i++)
            {
                if (networkBytes[i] != candidateBytes[i]) return false;
            }

            if (remainingBits == 0) return true;

            var mask = (byte)(0xFF << (8 - remainingBits));
            return (networkBytes[fullBytes] & mask) == (candidateBytes[fullBytes] & mask);
        }
    }
}

/// <summary>관리 화면 요청을 걸러내는 미들웨어.</summary>
public sealed class AdminNetworkMiddleware
{
    private readonly RequestDelegate _next;
    private readonly AdminAccessPolicy _policy;
    private readonly ILogger<AdminNetworkMiddleware> _logger;

    public AdminNetworkMiddleware(RequestDelegate next, AdminAccessPolicy policy,
        ILogger<AdminNetworkMiddleware> logger)
    {
        _next = next;
        _policy = policy;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // 클라이언트 API 는 직원 PC 가 써야 하므로 제한하지 않는다.
        // 장비 토큰으로 따로 인증하며, 자기 PC 정책만 받아 갈 수 있다.
        if (!_policy.Enabled || context.Request.Path.StartsWithSegments("/api"))
        {
            await _next(context);
            return;
        }

        var address = context.Connection.RemoteIpAddress;

        if (_policy.IsAllowed(address))
        {
            await _next(context);
            return;
        }

        _logger.LogWarning("허용되지 않은 주소에서 관리 화면에 접근하려 했습니다: {Address} {Path}",
            address, context.Request.Path);

        context.Response.StatusCode = StatusCodes.Status403Forbidden;
        context.Response.ContentType = "text/plain; charset=utf-8";

        await context.Response.WriteAsync(
            "이 PC 에서는 관리 화면에 접근할 수 없습니다.\n" +
            "관리자에게 문의해 주세요.");
    }
}

/// <summary>브라우저에 기본적인 보호를 걸어 두는 헤더.</summary>
public sealed class SecurityHeadersMiddleware
{
    private readonly RequestDelegate _next;

    public SecurityHeadersMiddleware(RequestDelegate next) => _next = next;

    public async Task InvokeAsync(HttpContext context)
    {
        var headers = context.Response.Headers;

        headers["X-Content-Type-Options"] = "nosniff";
        headers["X-Frame-Options"] = "DENY";
        headers["Referrer-Policy"] = "no-referrer";

        // 이 화면은 외부 자원을 전혀 쓰지 않으므로 자기 자신만 허용한다.
        headers["Content-Security-Policy"] =
            "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; " +
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'";

        await _next(context);
    }
}
