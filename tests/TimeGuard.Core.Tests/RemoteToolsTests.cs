using Hanil.TimeGuard.Core.Config;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

/// <summary>
/// 막을 원격 제어 프로그램 목록을 다루는 부분.
///
/// 실제로 프로그램을 멈추는 일은 Windows 에서만 되지만,
/// "무엇을 막을지" 정하는 계산은 여기서 전부 확인할 수 있다.
/// </summary>
public class RemoteToolsTests
{
    [Fact]
    public void 흔히_쓰는_원격_프로그램이_기본으로_들어_있다()
    {
        var names = RemoteTools.DefaultDisplayNames.ToList();

        Assert.Contains("TeamViewer", names);
        Assert.Contains("AnyDesk", names);
        Assert.Contains("RustDesk", names);
    }

    [Fact]
    public void 서비스로_상주하는_것도_함께_막는다()
    {
        // 서비스만 살아 있어도 로그아웃 상태에서 접속을 받아 준다.
        // 프로그램만 종료하고 서비스를 두면 막은 것이 아니다.
        var teamViewer = RemoteTools.Known.Single(t => t.DisplayName == "TeamViewer");

        Assert.NotEmpty(teamViewer.ProcessNames);
        Assert.NotEmpty(teamViewer.ServiceNames);
    }

    [Theory]
    [InlineData("TeamViewer.exe", "TeamViewer")]
    [InlineData("teamviewer.EXE", "teamviewer")]
    [InlineData("  AnyDesk  ", "AnyDesk")]
    [InlineData("사내원격.exe", "사내원격")]
    [InlineData("", "")]
    [InlineData(null, "")]
    public void 실행_파일_이름을_정리한다(string? input, string expected)
    {
        // 관리자가 ".exe" 를 붙여 적어도, 공백을 넣어도 같게 다뤄야 한다.
        Assert.Equal(expected, RemoteTools.Normalize(input));
    }

    [Fact]
    public void 관리자가_적은_이름이_목록에_더해진다()
    {
        var resolved = RemoteTools.Resolve(new[] { "사내원격도구" });

        Assert.Contains(resolved, t => t.DisplayName == "사내원격도구");
        Assert.True(resolved.Count > RemoteTools.Known.Length);
    }

    [Fact]
    public void 아무것도_적지_않으면_기본_목록만_쓴다()
    {
        var resolved = RemoteTools.Resolve(null);

        Assert.Equal(RemoteTools.Known.Length, resolved.Count);
    }

    [Fact]
    public void 이미_있는_프로그램을_적어도_중복되지_않는다()
    {
        var resolved = RemoteTools.Resolve(new[] { "TeamViewer", "AnyDesk.exe" });

        Assert.Equal(RemoteTools.Known.Length, resolved.Count);
    }

    [Fact]
    public void 빈_이름은_무시한다()
    {
        var resolved = RemoteTools.Resolve(new[] { "", "   ", ".exe" });

        Assert.Equal(RemoteTools.Known.Length, resolved.Count);
    }

    [Fact]
    public void 추가한_이름은_프로세스로_다룬다()
    {
        var resolved = RemoteTools.Resolve(new[] { "mytool.exe" });
        var added = resolved.Single(t => t.DisplayName == "mytool");

        Assert.Contains("mytool", added.ProcessNames);
        Assert.Empty(added.ServiceNames);
    }

    [Fact]
    public void 같은_프로그램이_여러_이름으로_돌_수_있다()
    {
        // 팀뷰어는 프로그램 본체와 서비스 프로세스 이름이 다르다.
        // 하나만 잡으면 나머지가 살아남는다.
        var teamViewer = RemoteTools.Known.Single(t => t.DisplayName == "TeamViewer");

        Assert.True(teamViewer.ProcessNames.Length > 1);
    }
}

/// <summary>원격 차단 설정이 설정 파일에 제대로 남는지.</summary>
public class RemoteBlockingConfigTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-remote-" + Guid.NewGuid().ToString("N"));

    private string ConfigPath => Path.Combine(_directory, "config.json");

    [Fact]
    public void 처음_설치하면_원격_차단은_모두_꺼져_있다()
    {
        // 켜 둔 채로 설치되면 원격으로 일하던 곳이 갑자기 막힌다.
        var config = GuardConfig.CreateInitial();

        Assert.False(config.BlockRemoteAccess);
        Assert.False(config.BlockRemoteTools);
        Assert.Empty(config.ExtraRemoteToolNames);
    }

    [Fact]
    public void 설정이_저장되고_다시_읽힌다()
    {
        var store = new ConfigStore(ConfigPath);
        var config = GuardConfig.CreateInitial();

        config.BlockRemoteAccess = true;
        config.BlockRemoteTools = true;
        config.ExtraRemoteToolNames = new List<string> { "사내원격", "mytool" };

        store.Save(config, "테스트");
        var loaded = store.Load(out var error);

        Assert.Null(error);
        Assert.True(loaded.BlockRemoteAccess);
        Assert.True(loaded.BlockRemoteTools);
        Assert.Equal(2, loaded.ExtraRemoteToolNames.Count);
        Assert.Contains("사내원격", loaded.ExtraRemoteToolNames);
    }

    [Fact]
    public void 설정_파일이_깨지면_차단이_켜진_채로_넘어가지_않는다()
    {
        Directory.CreateDirectory(_directory);
        File.WriteAllText(ConfigPath, "{ 이건 JSON 이 아닙니다");

        var loaded = new ConfigStore(ConfigPath).Load(out _);

        Assert.False(loaded.Enabled);
        Assert.False(loaded.BlockRemoteTools);
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}
