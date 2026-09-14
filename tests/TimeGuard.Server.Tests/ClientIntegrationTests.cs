using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 클라이언트(직원 PC)의 서버 연동 코드를 실제 서버에 붙여 확인한다.
/// 여기서 쓰는 ServerConnection 은 Windows 서비스가 그대로 쓰는 것과 같은 코드다.
/// </summary>
public class ClientIntegrationTests : IClassFixture<ServerFixture>, IDisposable
{
    private readonly ServerFixture _server;
    private readonly string _workDirectory;

    public ClientIntegrationTests(ServerFixture server)
    {
        _server = server;
        _workDirectory = Path.Combine(Path.GetTempPath(), "timeguard-client-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_workDirectory);
    }

    private string SettingsPath => Path.Combine(_workDirectory, "server.json");
    private string CachePath => Path.Combine(_workDirectory, "policy-cache.json");

    /// <summary>테스트 서버에 붙는 클라이언트를 만든다.</summary>
    private ServerConnection CreateConnection(ServerSettings settings) =>
        new(settings, SettingsPath, _server.Server.CreateHandler());

    private ServerSettings NewSettings() => new() { ServerUrl = "http://localhost" };

    [Fact]
    public async Task 클라이언트가_서버에_등록한다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        var key = await _server.GetEnrollmentKeyAsync();

        var (ok, message) = await connection.EnrollAsync("클라이언트-PC01", "HANIL\\hong", key);

        Assert.True(ok, message);
        Assert.True(settings.IsEnrolled);
        Assert.False(string.IsNullOrWhiteSpace(settings.DeviceId));

        // 다음 기동 때 쓰도록 설정 파일에 저장되어야 한다.
        var reloaded = ServerSettings.Load(SettingsPath);
        Assert.Equal(settings.Token, reloaded.Token);
        Assert.Equal(settings.DeviceId, reloaded.DeviceId);
    }

    [Fact]
    public async Task 등록_키가_틀리면_등록에_실패한다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);

        var (ok, message) = await connection.EnrollAsync("실패-PC", "user", "틀린키");

        Assert.False(ok);
        Assert.Contains("등록 키", message);
        Assert.False(settings.IsEnrolled);
    }

    [Fact]
    public async Task 서버에서_정책을_받아_온다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("정책-PC", "user", await _server.GetEnrollmentKeyAsync());

        var result = await connection.SyncAsync(
            new HeartbeatRequest { State = "Allowed", OsUser = "user" }, "정책-PC");

        Assert.True(result.Reached, result.Error);
        Assert.NotNull(result.NewPolicy);
        Assert.NotNull(result.PolicyStamp);

        var monday = result.NewPolicy!.Schedule.ForDay(DayOfWeek.Monday);
        Assert.Equal(new TimeOnly(9, 0), monday[0].Start);
    }

    [Fact]
    public async Task 정책이_그대로면_다시_받지_않는다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("표식-PC", "user", await _server.GetEnrollmentKeyAsync());

        var first = await connection.SyncAsync(new HeartbeatRequest { State = "Allowed" }, "표식-PC");

        var second = await connection.SyncAsync(
            new HeartbeatRequest { State = "Allowed", PolicyStamp = first.PolicyStamp }, "표식-PC");

        Assert.NotNull(first.NewPolicy);
        Assert.Null(second.NewPolicy);
        Assert.True(second.Reached);
    }

    [Fact]
    public async Task 서버에_닿지_못하면_실패로_알려_준다()
    {
        // 아무도 듣고 있지 않은 주소를 가리키게 한다.
        var settings = new ServerSettings
        {
            ServerUrl = "http://127.0.0.1:59999",
            DeviceId = "없는장비",
            Token = "없는토큰"
        };

        using var connection = new ServerConnection(settings, SettingsPath);

        var result = await connection.SyncAsync(new HeartbeatRequest { State = "Allowed" }, "끊김-PC");

        Assert.False(result.Reached);
        Assert.False(string.IsNullOrWhiteSpace(result.Error));
    }

    [Fact]
    public async Task 토큰이_거부되면_등록_키로_다시_등록한다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        var key = await _server.GetEnrollmentKeyAsync();

        await connection.EnrollAsync("재등록-PC", "user", key);
        var originalDeviceId = settings.DeviceId;

        // 서버 쪽 토큰을 바꿔 클라이언트 토큰이 통하지 않게 만든다.
        await _server.WithDbAsync(async db =>
        {
            var device = await db.Devices.FirstAsync(d => d.Id == originalDeviceId);
            device.TokenHash = SettingsServiceProbe.HashOf("전혀 다른 토큰");
            await db.SaveChangesAsync();
        });

        var result = await connection.SyncAsync(
            new HeartbeatRequest { State = "Allowed", OsUser = "user" }, "재등록-PC");

        Assert.True(result.Reached, result.Error);
        Assert.NotNull(result.NewPolicy);

        // 같은 장비로 다시 붙어야 서버 목록이 지저분해지지 않는다.
        Assert.Equal(originalDeviceId, settings.DeviceId);
    }

    [Fact]
    public async Task 연장_요청을_서버로_보낸다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("요청-클라이언트", "HANIL\\hong", await _server.GetEnrollmentKeyAsync());

        var (ok, message) = await connection.RequestExtensionAsync(60, "야근이 필요합니다", "HANIL\\hong");

        Assert.True(ok, message);

        var request = await _server.WithDbAsync(db =>
            db.ExtensionRequests.FirstAsync(r => r.DeviceId == settings.DeviceId));

        Assert.Equal(60, request.RequestedMinutes);
        Assert.Equal("야근이 필요합니다", request.Reason);
    }

    [Fact]
    public async Task 승인_결과를_받아_온다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("승인수신-PC", "user", await _server.GetEnrollmentKeyAsync());

        await connection.RequestExtensionAsync(90, "야근", "user");

        await _server.WithDbAsync(async db =>
        {
            var request = await db.ExtensionRequests.FirstAsync(r => r.DeviceId == settings.DeviceId);
            var device = await db.Devices.FirstAsync(d => d.Id == settings.DeviceId);

            var until = DateTimeOffset.Now.AddMinutes(60);
            request.Status = RequestStatus.Approved;
            request.GrantedMinutes = 60;
            request.GrantedUntil = until;
            request.DecidedAt = DateTimeOffset.Now;
            device.ExtensionUntil = until;

            await db.SaveChangesAsync();
        });

        var result = await connection.SyncAsync(new HeartbeatRequest { State = "Allowed" }, "승인수신-PC");

        Assert.NotNull(result.ExtensionUntil);
        Assert.Single(result.Decisions);
        Assert.Equal("Approved", result.Decisions[0].Status);
        Assert.Equal(60, result.Decisions[0].GrantedMinutes);
    }

    [Fact]
    public async Task 기록을_서버로_올린다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("기록올리기-PC", "user", await _server.GetEnrollmentKeyAsync());

        var uploaded = await connection.ReportEventsAsync(new List<EventEntry>
        {
            new() { At = DateTimeOffset.Now, Category = "조치", Message = "전원 차단을 실행했습니다." }
        });

        Assert.True(uploaded);

        var saved = await _server.WithDbAsync(db => db.DeviceEvents
            .Where(e => e.DeviceId == settings.DeviceId && e.Category == "조치")
            .CountAsync());

        Assert.Equal(1, saved);
    }

    // ---- 연결이 끊겼을 때를 대비한 정책 보관 ----

    [Fact]
    public void 받은_정책을_보관했다_다시_읽는다()
    {
        var cache = new PolicyCache(CachePath);

        var policy = GuardConfig.CreateInitial();
        policy.Enabled = true;
        policy.Schedule.SetDay(DayOfWeek.Monday, new[] { new TimeWindow(new TimeOnly(8, 0), new TimeOnly(17, 0)) });

        cache.Save(policy, "5-3");

        var loaded = cache.Load();

        Assert.NotNull(loaded);
        Assert.Equal("5-3", loaded!.Stamp);
        Assert.True(loaded.Policy.Enabled);
        Assert.Equal(new TimeOnly(8, 0), loaded.Policy.Schedule.ForDay(DayOfWeek.Monday)[0].Start);
    }

    [Fact]
    public void 보관된_정책이_없으면_null_을_돌려준다()
    {
        Assert.Null(new PolicyCache(CachePath).Load());
    }

    [Fact]
    public void 보관_파일이_깨져도_예외를_던지지_않는다()
    {
        File.WriteAllText(CachePath, "{ 이건 JSON 이 아닙니다");

        Assert.Null(new PolicyCache(CachePath).Load());
    }

    [Fact]
    public async Task 서버에서_받은_정책이_그대로_보관된다()
    {
        var settings = NewSettings();
        using var connection = CreateConnection(settings);
        await connection.EnrollAsync("보관-PC", "user", await _server.GetEnrollmentKeyAsync());

        var result = await connection.SyncAsync(new HeartbeatRequest { State = "Allowed" }, "보관-PC");

        var cache = new PolicyCache(CachePath);
        cache.Save(result.NewPolicy!, result.PolicyStamp!);

        var loaded = cache.Load();

        Assert.NotNull(loaded);
        Assert.Equal(result.PolicyStamp, loaded!.Stamp);

        // 랜선을 뽑아도 이 시간표로 계속 판정할 수 있어야 한다.
        var monday = loaded.Policy.Schedule.ForDay(DayOfWeek.Monday);
        Assert.Equal(new TimeOnly(9, 0), monday[0].Start);
        Assert.Equal(new TimeOnly(18, 0), monday[0].End);
    }

    [Fact]
    public void 서버_설정이_없으면_단독_모드다()
    {
        var settings = ServerSettings.Load(Path.Combine(_workDirectory, "없는파일.json"));

        Assert.False(settings.IsConfigured);
        Assert.False(settings.IsEnrolled);
    }

    public void Dispose()
    {
        try
        {
            if (Directory.Exists(_workDirectory)) Directory.Delete(_workDirectory, recursive: true);
        }
        catch (IOException)
        {
            // 정리 실패는 테스트 결과에 영향이 없다.
        }
    }
}

/// <summary>테스트에서 서버와 같은 방식으로 토큰 해시를 만들기 위한 도우미.</summary>
internal static class SettingsServiceProbe
{
    internal static string HashOf(string token) =>
        Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes(token)));
}
