using System.Collections.Concurrent;
using System.Net;

namespace Hanil.TimeGuard.Server.Security;

/// <summary>
/// 로그인 실패가 쌓이면 그 위치에서의 시도를 일정 시간 막는다.
///
/// 비밀번호는 PBKDF2 로 저장하므로 파일을 훔쳐도 바로 풀리지 않지만,
/// 로그인 화면에 계속 대입하는 것은 따로 막아야 한다.
/// </summary>
public sealed class LoginThrottle
{
    /// <summary>이 횟수만큼 실패하면 잠근다.</summary>
    public const int MaxAttempts = 5;

    /// <summary>잠기는 시간.</summary>
    public static readonly TimeSpan LockDuration = TimeSpan.FromMinutes(15);

    /// <summary>이 시간 동안 아무 시도가 없으면 실패 기록을 지운다.</summary>
    private static readonly TimeSpan AttemptWindow = TimeSpan.FromMinutes(15);

    private readonly ConcurrentDictionary<string, Attempts> _byOrigin = new();
    private readonly Func<DateTimeOffset> _now;

    public LoginThrottle() : this(() => DateTimeOffset.Now) { }

    /// <summary>테스트에서 시간을 흐르게 하기 위해 시계를 주입받는다.</summary>
    internal LoginThrottle(Func<DateTimeOffset> now) => _now = now;

    private sealed class Attempts
    {
        public int Failures;
        public DateTimeOffset LastFailure;
        public DateTimeOffset? LockedUntil;
    }

    /// <summary>지금 이 위치에서 로그인을 시도할 수 있는지.</summary>
    public bool IsAllowed(string origin, out TimeSpan retryAfter)
    {
        retryAfter = TimeSpan.Zero;

        if (!_byOrigin.TryGetValue(origin, out var attempts)) return true;

        lock (attempts)
        {
            if (attempts.LockedUntil is not { } until) return true;

            var now = _now();
            if (now >= until)
            {
                // 잠금이 풀렸다. 처음부터 다시 센다.
                attempts.LockedUntil = null;
                attempts.Failures = 0;
                return true;
            }

            retryAfter = until - now;
            return false;
        }
    }

    /// <summary>실패를 기록한다. 한도를 넘으면 잠긴다.</summary>
    public bool RecordFailure(string origin)
    {
        var attempts = _byOrigin.GetOrAdd(origin, _ => new Attempts());

        lock (attempts)
        {
            var now = _now();

            // 오래 전 실패는 잊는다. 어쩌다 한 번 틀린 것까지 누적하지 않는다.
            if (now - attempts.LastFailure > AttemptWindow) attempts.Failures = 0;

            attempts.Failures++;
            attempts.LastFailure = now;

            if (attempts.Failures < MaxAttempts) return false;

            attempts.LockedUntil = now + LockDuration;
            return true;
        }
    }

    /// <summary>로그인에 성공하면 기록을 지운다.</summary>
    public void RecordSuccess(string origin) => _byOrigin.TryRemove(origin, out _);

    /// <summary>남은 시도 횟수. 사용자에게 알려 주기 위한 값이다.</summary>
    public int RemainingAttempts(string origin)
    {
        if (!_byOrigin.TryGetValue(origin, out var attempts)) return MaxAttempts;

        lock (attempts)
        {
            if (_now() - attempts.LastFailure > AttemptWindow) return MaxAttempts;
            return Math.Max(0, MaxAttempts - attempts.Failures);
        }
    }

    /// <summary>
    /// 요청이 온 위치를 식별한다.
    /// 주소를 알 수 없으면 하나의 묶음으로 취급해, 식별이 안 된다는 이유로 제한을 빠져나가지 못하게 한다.
    /// </summary>
    public static string DescribeOrigin(IPAddress? address) =>
        address is null ? "(주소 불명)" : address.ToString();
}
