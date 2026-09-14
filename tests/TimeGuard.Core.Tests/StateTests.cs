using Hanil.TimeGuard.Core.State;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

/// <summary>
/// 허용 시간이 아닌데 반복해서 PC 를 켜는 것에 대한 대응.
///
/// 유예를 매번 똑같이 주면 껐다 켜기를 되풀이해 그 시간만큼씩 쓸 수 있다.
/// </summary>
public class BootAttemptTrackerTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-boot-" + Guid.NewGuid().ToString("N"));

    private BootAttemptTracker NewTracker() =>
        new(Path.Combine(_directory, "boot-attempts.json"));

    private static readonly DateTimeOffset Now =
        new(2026, 9, 14, 22, 0, 0, TimeSpan.FromHours(9));

    private static readonly TimeSpan BaseGrace = TimeSpan.FromSeconds(120);

    [Fact]
    public void 처음_켰을_때는_정해진_유예를_그대로_준다()
    {
        var grace = NewTracker().NextGrace(BaseGrace, Now, out var attempt);

        Assert.Equal(BaseGrace, grace);
        Assert.Equal(1, attempt);
    }

    [Fact]
    public void 다시_켤수록_유예가_짧아진다()
    {
        var tracker = NewTracker();

        var first = tracker.NextGrace(BaseGrace, Now, out _);
        var second = tracker.NextGrace(BaseGrace, Now.AddMinutes(3), out var secondAttempt);
        var third = tracker.NextGrace(BaseGrace, Now.AddMinutes(6), out var thirdAttempt);

        Assert.Equal(2, secondAttempt);
        Assert.Equal(3, thirdAttempt);

        Assert.True(second < first, $"{second} 이 {first} 보다 짧아야 합니다");
        Assert.True(third < second, $"{third} 이 {second} 보다 짧아야 합니다");
    }

    [Fact]
    public void 아무리_줄어도_저장할_시간은_남겨_준다()
    {
        var tracker = NewTracker();

        TimeSpan grace = BaseGrace;
        for (var i = 0; i < 20; i++)
            grace = tracker.NextGrace(BaseGrace, Now.AddMinutes(i), out _);

        Assert.True(grace >= TimeSpan.FromSeconds(15), $"유예가 너무 짧습니다: {grace}");
    }

    [Fact]
    public void 허용_시간이_되면_기록이_지워진다()
    {
        var tracker = NewTracker();

        tracker.NextGrace(BaseGrace, Now, out _);
        tracker.NextGrace(BaseGrace, Now.AddMinutes(3), out _);

        tracker.Reset();

        var grace = tracker.NextGrace(BaseGrace, Now.AddMinutes(6), out var attempt);

        Assert.Equal(1, attempt);
        Assert.Equal(BaseGrace, grace);
    }

    [Fact]
    public void 한참_지난_기록은_잊는다()
    {
        var tracker = NewTracker();

        tracker.NextGrace(BaseGrace, Now, out _);
        tracker.NextGrace(BaseGrace, Now.AddMinutes(3), out _);

        // 어제 있었던 일로 오늘 유예를 줄이면 안 된다.
        var grace = tracker.NextGrace(BaseGrace, Now.AddDays(1), out var attempt);

        Assert.Equal(1, attempt);
        Assert.Equal(BaseGrace, grace);
    }

    [Fact]
    public void PC_를_껐다_켜도_횟수를_기억한다()
    {
        var path = Path.Combine(_directory, "boot-attempts.json");

        new BootAttemptTracker(path).NextGrace(BaseGrace, Now, out _);

        // 서비스가 다시 뜬 상황을 흉내낸다.
        new BootAttemptTracker(path).NextGrace(BaseGrace, Now.AddMinutes(3), out var attempt);

        Assert.Equal(2, attempt);
    }

    [Fact]
    public void 유예가_원래_짧으면_더_줄이지_않는다()
    {
        var tracker = NewTracker();
        var shortGrace = TimeSpan.FromSeconds(10);

        var first = tracker.NextGrace(shortGrace, Now, out _);
        var second = tracker.NextGrace(shortGrace, Now.AddMinutes(1), out _);

        Assert.Equal(shortGrace, first);
        Assert.Equal(shortGrace, second);
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}

/// <summary>
/// 잠근 계정의 기록.
/// 이 기록이 없으면 어떤 계정을 풀어 줘야 할지 알 수 없어 직원이 로그인하지 못한 채 남는다.
/// </summary>
public class LockedAccountStoreTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-locked-" + Guid.NewGuid().ToString("N"));

    private string Path_ => Path.Combine(_directory, "locked-accounts.json");

    private LockedAccountStore NewStore() => new(Path_);

    [Fact]
    public void 처음에는_잠긴_계정이_없다()
    {
        Assert.Empty(NewStore().Load());
    }

    [Fact]
    public void 잠근_계정을_기록하고_읽는다()
    {
        var store = NewStore();

        store.Add("hong", "허용 시간이 끝났습니다.");

        var locked = store.Load();

        Assert.Single(locked);
        Assert.Equal("hong", locked[0].UserName);
        Assert.Equal("허용 시간이 끝났습니다.", locked[0].Reason);
    }

    [Fact]
    public void 같은_계정을_두_번_기록하지_않는다()
    {
        var store = NewStore();

        store.Add("hong", "첫 번째");
        store.Add("hong", "두 번째");

        Assert.Single(store.Load());
    }

    [Fact]
    public void 계정_이름의_대소문자를_구분하지_않는다()
    {
        var store = NewStore();

        store.Add("Hong", "잠금");
        store.Add("hong", "잠금");

        Assert.Single(store.Load());
    }

    [Fact]
    public void 풀어_준_계정은_목록에서_빠진다()
    {
        var store = NewStore();

        store.Add("hong", "잠금");
        store.Add("kim", "잠금");

        store.Remove("hong");

        var locked = store.Load();

        Assert.Single(locked);
        Assert.Equal("kim", locked[0].UserName);
    }

    [Fact]
    public void 서비스가_다시_떠도_기록이_남아_있다()
    {
        NewStore().Add("hong", "잠금");

        // 서비스가 다시 시작된 상황을 흉내낸다.
        var reloaded = new LockedAccountStore(Path_).Load();

        Assert.Single(reloaded);
        Assert.Equal("hong", reloaded[0].UserName);
    }

    [Fact]
    public void 기록_파일이_깨져도_예외를_던지지_않는다()
    {
        Directory.CreateDirectory(_directory);
        File.WriteAllText(Path_, "{ 이건 JSON 이 아닙니다");

        Assert.Empty(NewStore().Load());
    }

    [Fact]
    public void 모두_지울_수_있다()
    {
        var store = NewStore();

        store.Add("hong", "잠금");
        store.Add("kim", "잠금");

        store.Clear();

        Assert.Empty(store.Load());
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}
