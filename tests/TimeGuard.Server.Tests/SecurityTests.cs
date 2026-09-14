using System.Net;
using Hanil.TimeGuard.Server.Security;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>로그인 대입을 막는 제한 장치.</summary>
public class LoginThrottleTests
{
    /// <summary>테스트에서 시간을 마음대로 흐르게 한다.</summary>
    private sealed class Clock
    {
        public DateTimeOffset Now = new(2026, 9, 14, 9, 0, 0, TimeSpan.FromHours(9));
        public void Advance(TimeSpan amount) => Now += amount;
    }

    [Fact]
    public void 처음에는_로그인을_시도할_수_있다()
    {
        var throttle = new LoginThrottle();

        Assert.True(throttle.IsAllowed("192.168.0.5", out _));
        Assert.Equal(LoginThrottle.MaxAttempts, throttle.RemainingAttempts("192.168.0.5"));
    }

    [Fact]
    public void 한도만큼_틀리면_잠긴다()
    {
        var throttle = new LoginThrottle();

        for (var i = 1; i < LoginThrottle.MaxAttempts; i++)
        {
            Assert.False(throttle.RecordFailure("192.168.0.5"));
            Assert.True(throttle.IsAllowed("192.168.0.5", out _));
        }

        Assert.True(throttle.RecordFailure("192.168.0.5"));   // 마지막 실패에서 잠긴다
        Assert.False(throttle.IsAllowed("192.168.0.5", out var retryAfter));
        Assert.True(retryAfter > TimeSpan.Zero);
    }

    [Fact]
    public void 남은_시도_횟수를_알려_준다()
    {
        var throttle = new LoginThrottle();

        throttle.RecordFailure("192.168.0.5");
        throttle.RecordFailure("192.168.0.5");

        Assert.Equal(LoginThrottle.MaxAttempts - 2, throttle.RemainingAttempts("192.168.0.5"));
    }

    [Fact]
    public void 잠금은_시간이_지나면_풀린다()
    {
        var clock = new Clock();
        var throttle = new LoginThrottle(() => clock.Now);

        for (var i = 0; i < LoginThrottle.MaxAttempts; i++) throttle.RecordFailure("192.168.0.5");
        Assert.False(throttle.IsAllowed("192.168.0.5", out _));

        clock.Advance(LoginThrottle.LockDuration + TimeSpan.FromSeconds(1));

        Assert.True(throttle.IsAllowed("192.168.0.5", out _));
    }

    [Fact]
    public void 성공하면_실패_기록이_지워진다()
    {
        var throttle = new LoginThrottle();

        throttle.RecordFailure("192.168.0.5");
        throttle.RecordFailure("192.168.0.5");
        throttle.RecordSuccess("192.168.0.5");

        Assert.Equal(LoginThrottle.MaxAttempts, throttle.RemainingAttempts("192.168.0.5"));
    }

    [Fact]
    public void 한_PC_가_잠겨도_다른_PC_는_영향받지_않는다()
    {
        var throttle = new LoginThrottle();

        for (var i = 0; i < LoginThrottle.MaxAttempts; i++) throttle.RecordFailure("192.168.0.5");

        Assert.False(throttle.IsAllowed("192.168.0.5", out _));
        Assert.True(throttle.IsAllowed("192.168.0.9", out _));
    }

    [Fact]
    public void 오래_간격을_두고_틀린_것은_누적되지_않는다()
    {
        var clock = new Clock();
        var throttle = new LoginThrottle(() => clock.Now);

        // 어쩌다 한 번씩 틀리는 것까지 모아 잠그면 관리자가 곤란해진다.
        // 한도를 넘는 횟수를 틀려도, 사이가 충분히 벌어져 있으면 잠기지 않아야 한다.
        for (var i = 0; i < LoginThrottle.MaxAttempts + 2; i++)
        {
            var locked = throttle.RecordFailure("192.168.0.5");

            Assert.False(locked);
            Assert.True(throttle.IsAllowed("192.168.0.5", out _));

            clock.Advance(TimeSpan.FromMinutes(20));
        }
    }

    [Fact]
    public void 연달아_틀리면_남은_횟수가_줄어든다()
    {
        var clock = new Clock();
        var throttle = new LoginThrottle(() => clock.Now);

        throttle.RecordFailure("192.168.0.5");
        clock.Advance(TimeSpan.FromSeconds(30));
        throttle.RecordFailure("192.168.0.5");

        Assert.Equal(LoginThrottle.MaxAttempts - 2, throttle.RemainingAttempts("192.168.0.5"));
    }

    [Fact]
    public void 주소를_알_수_없어도_제한을_피할_수_없다()
    {
        var throttle = new LoginThrottle();
        var origin = LoginThrottle.DescribeOrigin(null);

        for (var i = 0; i < LoginThrottle.MaxAttempts; i++) throttle.RecordFailure(origin);

        Assert.False(throttle.IsAllowed(origin, out _));
    }
}

/// <summary>관리 화면을 열 수 있는 위치를 가르는 규칙.</summary>
public class AdminNetworkGuardTests
{
    private static AdminNetworkGuard Parse(string? text)
    {
        var guard = AdminNetworkGuard.Parse(text, out var problems);
        Assert.Empty(problems);
        return guard;
    }

    [Fact]
    public void 설정하지_않으면_모두_허용한다()
    {
        var guard = Parse(null);

        Assert.False(guard.Enabled);
        Assert.True(guard.IsAllowed(IPAddress.Parse("192.168.0.99")));
    }

    [Fact]
    public void 지정한_PC_만_허용한다()
    {
        var guard = Parse("192.168.0.5");

        Assert.True(guard.Enabled);
        Assert.True(guard.IsAllowed(IPAddress.Parse("192.168.0.5")));
        Assert.False(guard.IsAllowed(IPAddress.Parse("192.168.0.6")));
    }

    [Fact]
    public void 여러_주소를_적을_수_있다()
    {
        var guard = Parse("192.168.0.5, 192.168.0.7");

        Assert.True(guard.IsAllowed(IPAddress.Parse("192.168.0.5")));
        Assert.True(guard.IsAllowed(IPAddress.Parse("192.168.0.7")));
        Assert.False(guard.IsAllowed(IPAddress.Parse("192.168.0.6")));
    }

    [Theory]
    [InlineData("192.168.10.0/24", "192.168.10.1", true)]
    [InlineData("192.168.10.0/24", "192.168.10.254", true)]
    [InlineData("192.168.10.0/24", "192.168.11.1", false)]
    [InlineData("192.168.0.0/16", "192.168.99.5", true)]
    [InlineData("10.0.0.0/8", "10.5.6.7", true)]
    [InlineData("10.0.0.0/8", "11.5.6.7", false)]
    [InlineData("192.168.1.128/25", "192.168.1.200", true)]
    [InlineData("192.168.1.128/25", "192.168.1.100", false)]
    public void 대역으로도_지정할_수_있다(string rule, string candidate, bool expected)
    {
        var guard = Parse(rule);

        Assert.Equal(expected, guard.IsAllowed(IPAddress.Parse(candidate)));
    }

    [Fact]
    public void 서버_PC_자신은_언제나_허용한다()
    {
        // 주소를 잘못 넣어 아무도 들어가지 못하는 일이 없어야 한다.
        var guard = Parse("192.168.0.5");

        Assert.True(guard.IsAllowed(IPAddress.Loopback));
        Assert.True(guard.IsAllowed(IPAddress.IPv6Loopback));
    }

    [Fact]
    public void 주소를_알_수_없으면_막는다()
    {
        var guard = Parse("192.168.0.5");

        Assert.False(guard.IsAllowed(null));
    }

    [Fact]
    public void IPv6_으로_감싸인_IPv4_도_알아본다()
    {
        var guard = Parse("192.168.0.5");

        Assert.True(guard.IsAllowed(IPAddress.Parse("::ffff:192.168.0.5")));
        Assert.False(guard.IsAllowed(IPAddress.Parse("::ffff:192.168.0.6")));
    }

    [Theory]
    [InlineData("아무거나")]
    [InlineData("192.168.0.5/99")]
    [InlineData("999.999.999.999")]
    public void 잘못된_주소는_알려_준다(string text)
    {
        AdminNetworkGuard.Parse(text, out var problems);

        Assert.Single(problems);
    }

    [Fact]
    public void 잘못된_항목이_있어도_옳은_항목은_살린다()
    {
        var guard = AdminNetworkGuard.Parse("192.168.0.5, 이건틀림", out var problems);

        Assert.Single(problems);
        Assert.True(guard.IsAllowed(IPAddress.Parse("192.168.0.5")));
    }
}

/// <summary>웹 화면에서 바꾸는 접근 제한.</summary>
public class AdminAccessPolicyTests
{
    [Fact]
    public void 설정을_바꾸면_곧바로_적용된다()
    {
        var policy = new AdminAccessPolicy();

        Assert.True(policy.IsAllowed(IPAddress.Parse("192.168.0.9")));

        policy.Update("192.168.0.5");

        Assert.False(policy.IsAllowed(IPAddress.Parse("192.168.0.9")));
        Assert.True(policy.IsAllowed(IPAddress.Parse("192.168.0.5")));
    }

    [Fact]
    public void 비우면_제한이_풀린다()
    {
        var policy = new AdminAccessPolicy();
        policy.Update("192.168.0.5");

        policy.Update("");

        Assert.False(policy.Enabled);
        Assert.True(policy.IsAllowed(IPAddress.Parse("192.168.0.9")));
    }

    [Fact]
    public void 설정한_내용을_그대로_돌려준다()
    {
        var policy = new AdminAccessPolicy();
        policy.Update("  192.168.0.5, 10.0.0.0/8  ");

        Assert.Equal("192.168.0.5, 10.0.0.0/8", policy.Configured);
    }
}
