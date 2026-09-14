using System.Net;
using System.Net.Http.Json;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

public class DeviceApiTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public DeviceApiTests(ServerFixture server) => _server = server;

    // ---- 등록 ----

    [Fact]
    public async Task 올바른_등록_키로_PC를_등록한다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "등록테스트-PC");

        Assert.False(string.IsNullOrWhiteSpace(device.DeviceId));
        Assert.False(string.IsNullOrWhiteSpace(device.Token));
    }

    [Fact]
    public async Task 잘못된_등록_키는_거부한다()
    {
        var http = _server.CreateClient();

        var response = await http.PostAsJsonAsync(ServerRoutes.Enroll, new EnrollRequest
        {
            MachineName = "침입자PC",
            EnrollmentKey = "이건-틀린-키"
        }, IpcJson.Options);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);

        var error = await response.Content.ReadFromJsonAsync<ApiError>(IpcJson.Options);
        Assert.Contains("등록 키", error!.Message);
    }

    [Fact]
    public async Task PC_이름이_비면_거부한다()
    {
        var http = _server.CreateClient();
        var key = await _server.GetEnrollmentKeyAsync();

        var response = await http.PostAsJsonAsync(ServerRoutes.Enroll,
            new EnrollRequest { MachineName = "", EnrollmentKey = key }, IpcJson.Options);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task 같은_PC가_다시_등록하면_중복_생성되지_않는다()
    {
        const string machine = "재설치-PC";

        var first = await DeviceClient.EnrollAsync(_server, machine);
        var second = await DeviceClient.EnrollAsync(_server, machine);

        Assert.Equal(first.DeviceId, second.DeviceId);
        Assert.NotEqual(first.Token, second.Token); // 토큰은 새로 발급된다

        var count = await _server.WithDbAsync(db =>
            db.Devices.CountAsync(d => d.MachineName == machine));

        Assert.Equal(1, count);
    }

    [Fact]
    public async Task 재등록하면_이전_토큰은_더_이상_쓸_수_없다()
    {
        const string machine = "토큰교체-PC";

        var first = await DeviceClient.EnrollAsync(_server, machine);
        await DeviceClient.EnrollAsync(_server, machine);

        var response = await first.PostAsync(ServerRoutes.Heartbeat, new HeartbeatRequest());

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    // ---- 인증 ----

    [Fact]
    public async Task 토큰_없이는_하트비트를_받지_않는다()
    {
        var http = _server.CreateClient();

        var response = await http.PostAsJsonAsync(ServerRoutes.Heartbeat, new HeartbeatRequest(), IpcJson.Options);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task 위조한_토큰은_거부한다()
    {
        var http = _server.CreateClient();

        using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.Heartbeat)
        {
            Content = JsonContent.Create(new HeartbeatRequest(), options: IpcJson.Options)
        };
        request.Headers.Add(ServerRoutes.TokenHeader, "아무렇게나-만든-토큰");

        var response = await http.SendAsync(request);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    // ---- 정책 전달 ----

    [Fact]
    public async Task 하트비트로_기본_정책을_받는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "정책수신-PC");

        var response = await device.HeartbeatAsync();

        Assert.NotNull(response.Policy);
        Assert.True(response.Enforced);

        var monday = response.Policy!.Schedule.ForDay(DayOfWeek.Monday);
        Assert.Single(monday);
        Assert.Equal(new TimeOnly(9, 0), monday[0].Start);
        Assert.Equal(new TimeOnly(18, 0), monday[0].End);

        Assert.Empty(response.Policy.Schedule.ForDay(DayOfWeek.Saturday));
        Assert.Equal(GuardAction.Shutdown, response.Policy.Action);
    }

    [Fact]
    public async Task 정책이_그대로면_다시_보내지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "표식확인-PC");

        var first = await device.HeartbeatAsync();
        var second = await device.HeartbeatAsync(policyStamp: first.PolicyStamp);

        Assert.NotNull(first.Policy);
        Assert.Null(second.Policy); // 통신량을 아끼기 위해 생략된다
        Assert.Equal(first.PolicyStamp, second.PolicyStamp);
    }

    [Fact]
    public async Task 정책이_바뀌면_표식이_달라지고_다시_보낸다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "정책변경-PC");
        var before = await device.HeartbeatAsync();

        // 관리자가 이 PC 전용 시간표를 지정한 상황을 만든다.
        await _server.WithDbAsync(async db =>
        {
            var entity = await db.Devices.FirstAsync(d => d.Id == device.DeviceId);
            entity.UsesDefaultPolicy = false;
            entity.CustomScheduleJson = System.Text.Json.JsonSerializer.Serialize(
                BuildSchedule(new TimeOnly(6, 0), new TimeOnly(14, 0)), IpcJson.Options);
            entity.PolicyVersion++;
            await db.SaveChangesAsync();
        });

        var after = await device.HeartbeatAsync(policyStamp: before.PolicyStamp);

        Assert.NotEqual(before.PolicyStamp, after.PolicyStamp);
        Assert.NotNull(after.Policy);

        var monday = after.Policy!.Schedule.ForDay(DayOfWeek.Monday);
        Assert.Equal(new TimeOnly(6, 0), monday[0].Start);
        Assert.Equal(new TimeOnly(14, 0), monday[0].End);
    }

    [Fact]
    public async Task 제한을_끄면_클라이언트가_알_수_있다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "제한해제-PC");

        await _server.WithDbAsync(async db =>
        {
            var entity = await db.Devices.FirstAsync(d => d.Id == device.DeviceId);
            entity.Enforced = false;
            entity.PolicyVersion++;
            await db.SaveChangesAsync();
        });

        var response = await device.HeartbeatAsync();

        Assert.False(response.Enforced);
        Assert.False(response.Policy!.Enabled);
    }

    [Fact]
    public async Task 하트비트가_PC_상태를_서버에_남긴다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "상태보고-PC");

        await device.HeartbeatAsync(state: "Blocked", reason: "허용 시간대가 아닙니다");

        var entity = await _server.WithDbAsync(db =>
            db.Devices.FirstAsync(d => d.Id == device.DeviceId));

        Assert.Equal("Blocked", entity.LastState);
        Assert.Equal("허용 시간대가 아닙니다", entity.LastReason);
        Assert.NotNull(entity.LastSeenAt);
    }

    private static WeeklySchedule BuildSchedule(TimeOnly start, TimeOnly end)
    {
        var schedule = new WeeklySchedule();

        foreach (DayOfWeek day in Enum.GetValues<DayOfWeek>())
            schedule.SetDay(day, new[] { new TimeWindow(start, end) });

        return schedule;
    }
}
