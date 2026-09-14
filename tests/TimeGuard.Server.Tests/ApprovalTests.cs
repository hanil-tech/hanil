using System.Net;
using System.Net.Http.Json;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 등록 키 없이 PC 를 등록하는 흐름.
///
/// 직원 PC 가 자기를 알리면 승인 대기 목록에 오르고,
/// 관리자가 승인해야 비로소 시간표를 받아 간다.
/// 승인 전에는 아무것도 주지 않아야 한다.
/// </summary>
public class ApprovalTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public ApprovalTests(ServerFixture server) => _server = server;

    private static string NewClientId() =>
        Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(32));

    private async Task<AnnounceResponse> AnnounceAsync(string machineName, string clientId, string user = "HANIL\\tester")
    {
        var http = _server.CreateClient();

        var response = await http.PostAsJsonAsync(ServerRoutes.Announce, new AnnounceRequest
        {
            MachineName = machineName,
            OsUser = user,
            ClientId = clientId,
            ClientVersion = "테스트"
        }, IpcJson.Options);

        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<AnnounceResponse>(IpcJson.Options))!;
    }

    private async Task<ClaimResponse> ClaimAsync(string machineName, string clientId)
    {
        var http = _server.CreateClient();

        var response = await http.PostAsJsonAsync(ServerRoutes.Claim, new ClaimRequest
        {
            MachineName = machineName,
            ClientId = clientId
        }, IpcJson.Options);

        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<ClaimResponse>(IpcJson.Options))!;
    }

    /// <summary>관리자가 웹 화면에서 승인한 것과 같은 처리.</summary>
    private async Task SetApprovalAsync(string machineName, ApprovalState state)
    {
        await _server.WithDbAsync(async db =>
        {
            var device = await db.Devices.FirstAsync(d => d.MachineName == machineName);
            device.Approval = state;
            device.DecidedAt = DateTimeOffset.Now;
            device.DecidedBy = "admin";

            if (state == ApprovalState.Rejected) device.TokenHash = string.Empty;

            await db.SaveChangesAsync();
        });
    }

    // ---- 알리기 ----

    [Fact]
    public async Task 등록_키_없이_자기를_알릴_수_있다()
    {
        var response = await AnnounceAsync("알림-PC", NewClientId());

        Assert.Equal(ApprovalStates.Pending, response.State);
        Assert.False(string.IsNullOrWhiteSpace(response.Fingerprint));
    }

    [Fact]
    public async Task 알린_PC_는_승인_대기_목록에_오른다()
    {
        await AnnounceAsync("대기목록-PC", NewClientId());

        var device = await _server.WithDbAsync(db =>
            db.Devices.FirstAsync(d => d.MachineName == "대기목록-PC"));

        Assert.Equal(ApprovalState.Pending, device.Approval);
        Assert.NotNull(device.AnnouncedAt);
        Assert.False(string.IsNullOrWhiteSpace(device.ClientIdHash));
    }

    [Fact]
    public async Task 비밀값은_평문으로_저장되지_않는다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("비밀값-PC", clientId);

        var device = await _server.WithDbAsync(db =>
            db.Devices.FirstAsync(d => d.MachineName == "비밀값-PC"));

        Assert.NotEqual(clientId, device.ClientIdHash);
        Assert.Equal(64, device.ClientIdHash.Length);
    }

    [Fact]
    public async Task 같은_PC_가_여러_번_알려도_하나로_모인다()
    {
        var clientId = NewClientId();

        await AnnounceAsync("반복알림-PC", clientId);
        await AnnounceAsync("반복알림-PC", clientId);
        await AnnounceAsync("반복알림-PC", clientId);

        var count = await _server.WithDbAsync(db =>
            db.Devices.CountAsync(d => d.MachineName == "반복알림-PC"));

        Assert.Equal(1, count);
    }

    [Theory]
    [InlineData("", "0123456789012345678901234567890123456789")]
    [InlineData("이름은있음", "짧음")]
    [InlineData("이름은있음", "")]
    public async Task 잘못된_알림은_거부한다(string machineName, string clientId)
    {
        var http = _server.CreateClient();

        var response = await http.PostAsJsonAsync(ServerRoutes.Announce, new AnnounceRequest
        {
            MachineName = machineName,
            ClientId = clientId
        }, IpcJson.Options);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    // ---- 승인 전 ----

    [Fact]
    public async Task 승인_전에는_토큰을_주지_않는다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("승인전-PC", clientId);

        var claim = await ClaimAsync("승인전-PC", clientId);

        Assert.Equal(ApprovalStates.Pending, claim.State);
        Assert.Null(claim.Token);
        Assert.Null(claim.DeviceId);
    }

    [Fact]
    public async Task 모르는_비밀값으로는_토큰을_받을_수_없다()
    {
        await AnnounceAsync("남의PC", NewClientId());

        // 다른 사람이 아무 값이나 넣어 토큰을 가로채려는 상황.
        var claim = await ClaimAsync("남의PC", NewClientId());

        Assert.Null(claim.Token);
    }

    [Fact]
    public async Task 승인되지_않은_PC_는_정책을_받지_못한다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("정책차단-PC", clientId);
        await SetApprovalAsync("정책차단-PC", ApprovalState.Approved);

        var claim = await ClaimAsync("정책차단-PC", clientId);
        Assert.NotNull(claim.Token);

        // 관리자가 나중에 승인을 취소한 상황.
        await SetApprovalAsync("정책차단-PC", ApprovalState.Pending);

        var http = _server.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.Heartbeat)
        {
            Content = JsonContent.Create(new HeartbeatRequest { State = "Allowed" }, options: IpcJson.Options)
        };
        request.Headers.Add(ServerRoutes.TokenHeader, claim.Token!);

        var response = await http.SendAsync(request);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    // ---- 승인 후 ----

    [Fact]
    public async Task 승인하면_토큰을_받아_간다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("승인후-PC", clientId);
        await SetApprovalAsync("승인후-PC", ApprovalState.Approved);

        var claim = await ClaimAsync("승인후-PC", clientId);

        Assert.Equal(ApprovalStates.Approved, claim.State);
        Assert.False(string.IsNullOrWhiteSpace(claim.Token));
        Assert.False(string.IsNullOrWhiteSpace(claim.DeviceId));
    }

    [Fact]
    public async Task 승인_후에_정책을_받는다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("정책수신-승인-PC", clientId);
        await SetApprovalAsync("정책수신-승인-PC", ApprovalState.Approved);

        var claim = await ClaimAsync("정책수신-승인-PC", clientId);

        var http = _server.CreateClient();
        using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.Heartbeat)
        {
            Content = JsonContent.Create(new HeartbeatRequest { State = "Allowed" }, options: IpcJson.Options)
        };
        request.Headers.Add(ServerRoutes.TokenHeader, claim.Token!);

        var response = await http.SendAsync(request);
        response.EnsureSuccessStatusCode();

        var body = await response.Content.ReadFromJsonAsync<HeartbeatResponse>(IpcJson.Options);

        Assert.NotNull(body!.Policy);
        Assert.Equal(new TimeOnly(9, 0), body.Policy!.Schedule.ForDay(DayOfWeek.Monday)[0].Start);
    }

    // ---- 거절 ----

    [Fact]
    public async Task 거절하면_토큰을_주지_않는다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("거절-PC", clientId);
        await SetApprovalAsync("거절-PC", ApprovalState.Rejected);

        var claim = await ClaimAsync("거절-PC", clientId);

        Assert.Equal(ApprovalStates.Rejected, claim.State);
        Assert.Null(claim.Token);
    }

    [Fact]
    public async Task 거절한_PC_가_다시_알려도_대기로_돌아오지_않는다()
    {
        var clientId = NewClientId();
        await AnnounceAsync("거절재알림-PC", clientId);
        await SetApprovalAsync("거절재알림-PC", ApprovalState.Rejected);

        var again = await AnnounceAsync("거절재알림-PC", clientId);

        // 거절한 PC 가 계속 목록에 올라오면 관리자가 지친다.
        Assert.Equal(ApprovalStates.Rejected, again.State);
    }

    // ---- 등록 키 방식도 그대로 동작해야 한다 ----

    [Fact]
    public async Task 등록_키로_등록하면_승인_없이_바로_쓴다()
    {
        // 여러 대를 한꺼번에 설치할 때 쓰는 경로다.
        var device = await DeviceClient.EnrollAsync(_server, "키등록-PC");

        var entity = await _server.WithDbAsync(db =>
            db.Devices.FirstAsync(d => d.Id == device.DeviceId));

        Assert.Equal(ApprovalState.Approved, entity.Approval);

        var response = await device.HeartbeatAsync();
        Assert.NotNull(response.Policy);
    }
}
