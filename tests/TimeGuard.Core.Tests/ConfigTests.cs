using Hanil.TimeGuard.Core.Config;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

public class PasswordHasherTests
{
    [Fact]
    public void 올바른_비밀번호를_검증한다()
    {
        var hash = PasswordHasher.Hash("hanil-1234", iterations: 1000);

        Assert.True(PasswordHasher.Verify("hanil-1234", hash));
    }

    [Fact]
    public void 틀린_비밀번호는_거부한다()
    {
        var hash = PasswordHasher.Hash("hanil-1234", iterations: 1000);

        Assert.False(PasswordHasher.Verify("hanil-12345", hash));
        Assert.False(PasswordHasher.Verify("", hash));
    }

    [Fact]
    public void 같은_비밀번호도_매번_다른_해시가_된다()
    {
        var a = PasswordHasher.Hash("hanil-1234", iterations: 1000);
        var b = PasswordHasher.Hash("hanil-1234", iterations: 1000);

        Assert.NotEqual(a, b);
        Assert.True(PasswordHasher.Verify("hanil-1234", a));
        Assert.True(PasswordHasher.Verify("hanil-1234", b));
    }

    [Theory]
    [InlineData("")]
    [InlineData("not-a-hash")]
    [InlineData("pbkdf2$abc$xx$yy")]
    [InlineData("pbkdf2$1000$@@@$yy")]
    [InlineData("other$1000$AAAA$BBBB")]
    public void 손상된_해시_문자열은_안전하게_거부한다(string stored)
    {
        Assert.False(PasswordHasher.Verify("hanil-1234", stored));
    }

    [Theory]
    [InlineData("hanil-1234", true)]
    [InlineData("short1", false)]
    [InlineData("12345678", false)]
    [InlineData("   ", false)]
    public void 비밀번호_최소_조건을_확인한다(string password, bool expected)
    {
        Assert.Equal(expected, PasswordHasher.IsAcceptable(password, out _));
    }
}

public class TimeWindowTests
{
    [Theory]
    [InlineData("09:00-18:00", 9, 0, 18, 0)]
    [InlineData("9:00~18:00", 9, 0, 18, 0)]
    [InlineData("22:00-06:00", 22, 0, 6, 0)]
    [InlineData("08:30 - 17:30", 8, 30, 17, 30)]
    [InlineData("00:00-24:00", 0, 0, 0, 0)]
    public void 시간대_문자열을_해석한다(string text, int sh, int sm, int eh, int em)
    {
        Assert.True(TimeWindow.TryParse(text, out var window));
        Assert.Equal(new TimeOnly(sh, sm), window.Start);
        Assert.Equal(new TimeOnly(eh, em), window.End);
    }

    [Theory]
    [InlineData("")]
    [InlineData("09:00")]
    [InlineData("25:00-26:00")]
    [InlineData("abc-def")]
    public void 잘못된_시간대_문자열은_거부한다(string text)
    {
        Assert.False(TimeWindow.TryParse(text, out _));
    }

    [Fact]
    public void 자정을_넘기는_구간의_길이를_계산한다()
    {
        var window = new TimeWindow(new TimeOnly(22, 0), new TimeOnly(6, 0));

        Assert.True(window.CrossesMidnight);
        Assert.Equal(TimeSpan.FromHours(8), window.Duration);
    }

    [Fact]
    public void 종일_구간의_길이는_24시간이다()
    {
        var window = new TimeWindow(TimeOnly.MinValue, TimeOnly.MinValue);

        Assert.Equal(TimeSpan.FromDays(1), window.Duration);
    }
}

public class ConfigStoreTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-test-" + Guid.NewGuid().ToString("N"));

    private string ConfigPath => Path.Combine(_directory, "config.json");

    [Fact]
    public void 저장한_설정을_그대로_다시_읽는다()
    {
        var store = new ConfigStore(ConfigPath);
        var config = GuardConfig.CreateInitial();
        config.Enabled = true;
        config.Action = GuardAction.LogOff;
        config.PasswordHash = PasswordHasher.Hash("hanil-1234", 1000);
        config.Schedule.SetDay(DayOfWeek.Monday, new[] { new TimeWindow(new TimeOnly(8, 30), new TimeOnly(17, 30)) });
        config.AddHoliday(new DateOnly(2026, 1, 1));
        config.ExemptUsers.Add("admin");

        store.Save(config, "테스트");
        var loaded = store.Load(out var error);

        Assert.Null(error);
        Assert.True(loaded.Enabled);
        Assert.Equal(GuardAction.LogOff, loaded.Action);
        Assert.True(PasswordHasher.Verify("hanil-1234", loaded.PasswordHash));
        Assert.Equal(new TimeOnly(8, 30), loaded.Schedule.ForDay(DayOfWeek.Monday)[0].Start);
        Assert.True(loaded.IsHoliday(new DateOnly(2026, 1, 1)));
        Assert.Contains("admin", loaded.ExemptUsers);
    }

    [Fact]
    public void 설정_파일이_없으면_감시가_꺼진_기본값을_돌려준다()
    {
        var loaded = new ConfigStore(ConfigPath).Load(out var error);

        Assert.NotNull(error);
        Assert.False(loaded.Enabled);
    }

    [Fact]
    public void 설정_파일이_깨졌어도_차단하지_않는_기본값으로_동작한다()
    {
        Directory.CreateDirectory(_directory);
        File.WriteAllText(ConfigPath, "{ 이건 JSON 이 아닙니다 ");

        var loaded = new ConfigStore(ConfigPath).Load(out var error);

        Assert.NotNull(error);
        Assert.False(loaded.Enabled); // 절대로 켜진 상태로 넘어가면 안 된다
    }

    [Fact]
    public void 시간은_사람이_읽을_수_있는_형식으로_저장된다()
    {
        var store = new ConfigStore(ConfigPath);
        var config = GuardConfig.CreateInitial();
        store.Save(config, "테스트");

        var json = File.ReadAllText(ConfigPath);

        Assert.Contains("\"09:00\"", json);
        Assert.Contains("\"Shutdown\"", json); // 열거형이 숫자가 아닌 이름으로 저장되는지
    }

    [Fact]
    public void 덮어쓰기를_해도_설정이_유지된다()
    {
        var store = new ConfigStore(ConfigPath);
        var config = GuardConfig.CreateInitial();

        store.Save(config, "1차");
        config.Enabled = true;
        store.Save(config, "2차");

        var loaded = store.Load(out var error);

        Assert.Null(error);
        Assert.True(loaded.Enabled);
        Assert.Equal("2차", loaded.LastModifiedBy);
        Assert.False(File.Exists(ConfigPath + ".tmp"));
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}

public class AuditLogTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-log-" + Guid.NewGuid().ToString("N"));

    [Fact]
    public void 기록한_내용을_다시_읽을_수_있다()
    {
        var log = new AuditLog(Path.Combine(_directory, "t.log"));

        log.Write("조치", "전원 차단 실행");
        log.Write("설정", "허용 시간대 변경");

        var lines = log.Tail(10);

        Assert.Equal(2, lines.Count);
        Assert.Contains("전원 차단 실행", lines[0]);
        Assert.Contains("[설정]", lines[1]);
    }

    [Fact]
    public void 요청한_줄_수만큼만_돌려준다()
    {
        var log = new AuditLog(Path.Combine(_directory, "t.log"));
        for (var i = 0; i < 10; i++) log.Write("조치", $"{i}번째");

        var lines = log.Tail(3);

        Assert.Equal(3, lines.Count);
        Assert.Contains("9번째", lines[2]);
    }

    [Fact]
    public void 로그_파일이_없어도_예외를_던지지_않는다()
    {
        var lines = new AuditLog(Path.Combine(_directory, "missing.log")).Tail(10);

        Assert.Empty(lines);
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}
