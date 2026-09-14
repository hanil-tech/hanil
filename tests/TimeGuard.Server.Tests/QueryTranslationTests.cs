using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 화면에서 쓰는 조회가 SQLite 에서 실제로 실행되는지 확인한다.
///
/// SQLite 는 DateTimeOffset 을 ORDER BY 에 쓰지 못해, 시각으로 정렬하는 화면이
/// 전부 500 오류를 내는 일이 있었다. 저장 방식을 UTC 틱으로 바꿔 해결했고
/// 같은 일이 다시 생기지 않도록 여기서 잡는다.
/// </summary>
public class QueryTranslationTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public QueryTranslationTests(ServerFixture server) => _server = server;

    [Fact]
    public async Task 기록을_최신순으로_정렬할_수_있다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "정렬-기록-PC");

        await device.PostAsync(ServerRoutes.Events, new EventReport
        {
            Entries = new List<EventEntry>
            {
                new() { At = DateTimeOffset.Now.AddMinutes(-10), Category = "조치", Message = "먼저 일어난 일" },
                new() { At = DateTimeOffset.Now, Category = "조치", Message = "나중에 일어난 일" }
            }
        });

        var messages = await _server.WithDbAsync(db => db.DeviceEvents
            .Where(e => e.DeviceId == device.DeviceId && e.Category == "조치")
            .OrderByDescending(e => e.At)
            .Select(e => e.Message)
            .ToListAsync());

        Assert.Equal("나중에 일어난 일", messages[0]);
        Assert.Equal("먼저 일어난 일", messages[1]);
    }

    [Fact]
    public async Task 연장_요청을_처리_시각순으로_정렬할_수_있다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "정렬-요청-PC");

        await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 30, Reason = "첫 번째" });

        await _server.WithDbAsync(async db =>
        {
            var request = await db.ExtensionRequests.FirstAsync(r => r.DeviceId == device.DeviceId);
            request.Status = RequestStatus.Approved;
            request.DecidedAt = DateTimeOffset.Now;
            await db.SaveChangesAsync();
        });

        var decided = await _server.WithDbAsync(db => db.ExtensionRequests
            .Where(r => r.Status != RequestStatus.Pending)
            .OrderByDescending(r => r.DecidedAt)
            .Take(10)
            .ToListAsync());

        Assert.NotEmpty(decided);
    }

    [Fact]
    public async Task 장비를_마지막_연결_시각순으로_정렬할_수_있다()
    {
        await DeviceClient.EnrollAsync(_server, "정렬-장비-PC");

        var devices = await _server.WithDbAsync(db => db.Devices
            .OrderByDescending(d => d.LastSeenAt)
            .ThenBy(d => d.MachineName)
            .ToListAsync());

        Assert.NotEmpty(devices);
    }

    [Fact]
    public async Task 시각_범위로_걸러낼_수_있다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "범위조회-PC");
        await device.HeartbeatAsync();

        var cutoff = DateTimeOffset.Now.AddMinutes(-5);

        var recent = await _server.WithDbAsync(db => db.Devices
            .Where(d => d.LastSeenAt != null && d.LastSeenAt > cutoff)
            .CountAsync());

        Assert.True(recent >= 1);
    }

    [Fact]
    public async Task 저장했다_읽으면_같은_시점을_가리킨다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "시각왕복-PC");
        var before = DateTimeOffset.Now;

        await device.HeartbeatAsync();

        var lastSeen = await _server.WithDbAsync(db => db.Devices
            .Where(d => d.Id == device.DeviceId)
            .Select(d => d.LastSeenAt)
            .FirstAsync());

        Assert.NotNull(lastSeen);

        // UTC 로 저장되지만 가리키는 시점은 그대로여야 한다.
        var difference = (lastSeen!.Value - before).Duration();
        Assert.True(difference < TimeSpan.FromMinutes(1), $"차이가 너무 큽니다: {difference}");
    }

    [Fact]
    public async Task 클라이언트에는_지역_시각으로_내려간다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "지역시각-PC");

        await _server.WithDbAsync(async db =>
        {
            var entity = await db.Devices.FirstAsync(d => d.Id == device.DeviceId);
            entity.ExtensionUntil = DateTimeOffset.Now.AddHours(1);
            await db.SaveChangesAsync();
        });

        var response = await device.HeartbeatAsync();

        Assert.NotNull(response.ExtensionUntil);

        // 서버가 보는 지역 시각과 같은 오프셋이어야 클라이언트 화면에 올바로 표시된다.
        Assert.Equal(DateTimeOffset.Now.Offset, response.ExtensionUntil!.Value.Offset);
    }
}
