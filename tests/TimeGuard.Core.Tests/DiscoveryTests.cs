using System.Text;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

/// <summary>사내망 서버 검색이 주고받는 내용.</summary>
public class ServerDiscoveryTests
{
    [Fact]
    public void 문의와_응답_표시가_정해져_있다()
    {
        // 엉뚱한 프로그램의 신호를 우리 응답으로 오해하면 안 된다.
        Assert.False(string.IsNullOrWhiteSpace(ServerDiscovery.Question));
        Assert.False(string.IsNullOrWhiteSpace(ServerDiscovery.AnswerPrefix));
        Assert.NotEqual(ServerDiscovery.Question, ServerDiscovery.AnswerPrefix);
    }

    [Fact]
    public void 서버_정보를_주고받을_수_있다()
    {
        var original = new DiscoveredServer
        {
            Url = "https://192.168.0.10:8443",
            MachineName = "사무실-서버",
            Version = "1.0.0"
        };

        var wire = ServerDiscovery.AnswerPrefix + IpcJson.Serialize(original);

        Assert.StartsWith(ServerDiscovery.AnswerPrefix, wire);

        var payload = wire[ServerDiscovery.AnswerPrefix.Length..];
        var restored = IpcJson.Deserialize<DiscoveredServer>(payload);

        Assert.NotNull(restored);
        Assert.Equal(original.Url, restored!.Url);
        Assert.Equal("사무실-서버", restored.MachineName);
    }

    [Fact]
    public async Task 서버가_없으면_빈_목록을_돌려준다()
    {
        // 서버를 찾지 못하는 것은 오류가 아니다. 주소를 직접 적어 등록할 수 있다.
        var found = await ServerDiscovery.FindAsync(TimeSpan.FromMilliseconds(300));

        Assert.NotNull(found);
    }

    [Fact]
    public void 응답_표시가_없는_신호는_무시한다()
    {
        var noise = Encoding.UTF8.GetString(Encoding.UTF8.GetBytes("다른 프로그램의 신호입니다"));

        Assert.False(noise.StartsWith(ServerDiscovery.AnswerPrefix, StringComparison.Ordinal));
    }
}

/// <summary>서버 접속 설정.</summary>
public class ServerSettingsTests : IDisposable
{
    private readonly string _directory =
        Path.Combine(Path.GetTempPath(), "timeguard-settings-" + Guid.NewGuid().ToString("N"));

    private string Path_ => System.IO.Path.Combine(_directory, "server.json");

    [Fact]
    public void 설정_파일이_없으면_단독_모드다()
    {
        var settings = ServerSettings.Load(Path_);

        Assert.False(settings.IsConfigured);
        Assert.False(settings.IsEnrolled);
    }

    [Fact]
    public void 저장한_설정을_다시_읽는다()
    {
        Directory.CreateDirectory(_directory);

        var settings = new ServerSettings
        {
            ServerUrl = "https://192.168.0.10:8443",
            DeviceId = "abc123",
            Token = "비밀토큰",
            EnrollmentKey = "AAAAA-BBBBB-CCCCC-DDDDD",
            CertificateThumbprint = "ABCDEF0123456789"
        };

        settings.Save(Path_);
        var loaded = ServerSettings.Load(Path_);

        Assert.True(loaded.IsEnrolled);
        Assert.Equal(settings.DeviceId, loaded.DeviceId);
        Assert.Equal(settings.CertificateThumbprint, loaded.CertificateThumbprint);
    }

    [Theory]
    [InlineData("https://192.168.0.10:8443", true)]
    [InlineData("HTTPS://192.168.0.10:8443", true)]
    [InlineData("http://192.168.0.10:8080", false)]
    [InlineData("", false)]
    public void 암호화_여부를_알아본다(string url, bool expected)
    {
        var settings = new ServerSettings { ServerUrl = url };

        Assert.Equal(expected, settings.UsesHttps);
    }

    [Fact]
    public void 파일이_깨졌어도_단독_모드로_넘어간다()
    {
        Directory.CreateDirectory(_directory);
        File.WriteAllText(Path_, "{ 이건 JSON 이 아닙니다");

        var settings = ServerSettings.Load(Path_);

        Assert.False(settings.IsConfigured);
    }

    public void Dispose()
    {
        if (Directory.Exists(_directory)) Directory.Delete(_directory, recursive: true);
    }
}
