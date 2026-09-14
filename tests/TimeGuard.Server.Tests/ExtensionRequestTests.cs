using System.Net;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 직원이 연장을 요청하고 관리자가 승인하는 흐름 전체를 확인한다.
/// </summary>
public class ExtensionRequestTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public ExtensionRequestTests(ServerFixture server) => _server = server;

    [Fact]
    public async Task 연장을_요청하면_대기_상태로_쌓인다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "요청-PC");

        var response = await device.PostAsync(ServerRoutes.ExtensionRequests, new ExtensionRequestInput
        {
            Minutes = 60,
            Reason = "납기 때문에 야근합니다",
            OsUser = "HANIL\\hong"
        });

        response.EnsureSuccessStatusCode();

        var request = await _server.WithDbAsync(db =>
            db.ExtensionRequests.FirstAsync(r => r.DeviceId == device.DeviceId));

        Assert.Equal(RequestStatus.Pending, request.Status);
        Assert.Equal(60, request.RequestedMinutes);
        Assert.Equal("납기 때문에 야근합니다", request.Reason);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-10)]
    [InlineData(9999)]
    public async Task 범위를_벗어난_요청은_거부한다(int minutes)
    {
        var device = await DeviceClient.EnrollAsync(_server, $"범위-PC-{minutes}");

        var response = await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = minutes, Reason = "테스트" });

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task 대기_중인_요청을_무한정_쌓을_수_없다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "도배-PC");

        for (var i = 0; i < 3; i++)
        {
            var accepted = await device.PostAsync(ServerRoutes.ExtensionRequests,
                new ExtensionRequestInput { Minutes = 30, Reason = $"{i}번째" });

            accepted.EnsureSuccessStatusCode();
        }

        var rejected = await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 30, Reason = "네 번째" });

        Assert.Equal(HttpStatusCode.BadRequest, rejected.StatusCode);
    }

    [Fact]
    public async Task 승인하면_해당_PC에_연장이_적용된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "승인-PC");

        await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 90, Reason = "야근" });

        // 승인 전에는 연장이 없어야 한다.
        var before = await device.HeartbeatAsync();
        Assert.Null(before.ExtensionUntil);

        await ApproveAsync(device.DeviceId, grantedMinutes: 60);

        var after = await device.HeartbeatAsync();

        Assert.NotNull(after.ExtensionUntil);
        Assert.True(after.ExtensionUntil > DateTimeOffset.Now.AddMinutes(55));
        Assert.True(after.ExtensionUntil < DateTimeOffset.Now.AddMinutes(65));
    }

    [Fact]
    public async Task 승인_결과가_클라이언트에_한_번만_전달된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "알림-PC");

        await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 30, Reason = "확인용" });

        await ApproveAsync(device.DeviceId, grantedMinutes: 30);

        var first = await device.HeartbeatAsync();
        var second = await device.HeartbeatAsync();

        Assert.Single(first.Decisions);
        Assert.Equal(nameof(RequestStatus.Approved), first.Decisions[0].Status);
        Assert.Equal(30, first.Decisions[0].GrantedMinutes);

        // 같은 알림이 반복되면 사용자가 계속 같은 창을 보게 된다.
        Assert.Empty(second.Decisions);
    }

    [Fact]
    public async Task 거절도_사용자에게_전달된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "거절-PC");

        await device.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 120, Reason = "사유 없음" });

        await _server.WithDbAsync(async db =>
        {
            var request = await db.ExtensionRequests.FirstAsync(r => r.DeviceId == device.DeviceId);
            request.Status = RequestStatus.Denied;
            request.DecidedAt = DateTimeOffset.Now;
            request.DecidedBy = "admin";
            request.DecisionNote = "사전 결재가 필요합니다";
            await db.SaveChangesAsync();
        });

        var response = await device.HeartbeatAsync();

        Assert.Single(response.Decisions);
        Assert.Equal(nameof(RequestStatus.Denied), response.Decisions[0].Status);
        Assert.Equal("사전 결재가 필요합니다", response.Decisions[0].Note);
        Assert.Null(response.ExtensionUntil); // 거절이므로 연장은 없다
    }

    [Fact]
    public async Task 다른_PC의_요청은_보이지_않는다()
    {
        var mine = await DeviceClient.EnrollAsync(_server, "내PC");
        var other = await DeviceClient.EnrollAsync(_server, "남의PC");

        await other.PostAsync(ServerRoutes.ExtensionRequests,
            new ExtensionRequestInput { Minutes = 30, Reason = "남의 요청" });

        await ApproveAsync(other.DeviceId, grantedMinutes: 30);

        var response = await mine.HeartbeatAsync();

        Assert.Empty(response.Decisions);
        Assert.Null(response.ExtensionUntil);
    }

    [Fact]
    public async Task 이벤트_보고가_기록으로_남는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "기록-PC");

        var response = await device.PostAsync(ServerRoutes.Events, new EventReport
        {
            Entries = new List<EventEntry>
            {
                new() { At = DateTimeOffset.Now, Category = "조치", Message = "전원 차단을 실행했습니다." },
                new() { At = DateTimeOffset.Now, Category = "경고", Message = "종료 10분 전 안내" }
            }
        });

        response.EnsureSuccessStatusCode();

        var messages = await _server.WithDbAsync(db => db.DeviceEvents
            .Where(e => e.DeviceId == device.DeviceId && e.Category != "등록")
            .Select(e => e.Message)
            .ToListAsync());

        Assert.Contains("전원 차단을 실행했습니다.", messages);
        Assert.Contains("종료 10분 전 안내", messages);
    }

    /// <summary>관리자가 웹 화면에서 승인한 것과 같은 처리를 한다.</summary>
    private async Task ApproveAsync(string deviceId, int grantedMinutes)
    {
        await _server.WithDbAsync(async db =>
        {
            var request = await db.ExtensionRequests
                .FirstAsync(r => r.DeviceId == deviceId && r.Status == RequestStatus.Pending);

            var until = DateTimeOffset.Now.AddMinutes(grantedMinutes);

            request.Status = RequestStatus.Approved;
            request.GrantedMinutes = grantedMinutes;
            request.GrantedUntil = until;
            request.DecidedAt = DateTimeOffset.Now;
            request.DecidedBy = "admin";

            var device = await db.Devices.FirstAsync(d => d.Id == deviceId);
            if (device.ExtensionUntil is not { } existing || existing < until)
                device.ExtensionUntil = until;

            await db.SaveChangesAsync();
        });
    }
}
