using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 직원이 관리자 권한으로 로그인한 PC 를 찾아내는 기능.
///
/// 이런 PC 는 서비스를 멈춰 시간 제한을 무력화할 수 있고 계정 잠금도 통하지 않는다.
/// 관리자가 어느 PC 를 손봐야 하는지 알 수 있어야 한다.
/// </summary>
public class AdminRightsTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public AdminRightsTests(ServerFixture server) => _server = server;

    private async Task<Device> ReadDeviceAsync(string deviceId) =>
        await _server.WithDbAsync(db => db.Devices.FirstAsync(d => d.Id == deviceId));

    /// <summary>하트비트를 보내며 관리자 권한 여부를 함께 알린다.</summary>
    private static async Task ReportAsync(DeviceClient device, bool? isAdministrator)
    {
        var response = await device.PostAsync(ServerRoutes.Heartbeat, new HeartbeatRequest
        {
            State = "Allowed",
            OsUser = "HANIL\\hong",
            UserIsAdministrator = isAdministrator
        });

        response.EnsureSuccessStatusCode();
    }

    [Fact]
    public async Task 관리자_권한으로_로그인하면_서버가_안다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "관리자권한-PC");

        await ReportAsync(device, true);

        var saved = await ReadDeviceAsync(device.DeviceId);
        Assert.True(saved.LastUserIsAdministrator);
    }

    [Fact]
    public async Task 일반_사용자면_그렇게_기록된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "일반사용자-PC");

        await ReportAsync(device, false);

        var saved = await ReadDeviceAsync(device.DeviceId);
        Assert.False(saved.LastUserIsAdministrator);
    }

    [Fact]
    public async Task 확인하지_못한_경우에는_섣불리_단정하지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "확인불가-PC");

        await ReportAsync(device, null);

        var saved = await ReadDeviceAsync(device.DeviceId);

        // 모르는 것을 "관리자" 로 적으면 관리자가 헛걸음하게 된다.
        Assert.Null(saved.LastUserIsAdministrator);
    }

    [Fact]
    public async Task 관리자_권한이_발견되면_기록에_남는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "권한기록-PC");

        await ReportAsync(device, true);

        var security = await _server.WithDbAsync(db => db.DeviceEvents
            .Where(e => e.DeviceId == device.DeviceId && e.Category == "보안")
            .ToListAsync());

        Assert.Single(security);
        Assert.Contains("관리자", security[0].Message);
    }

    [Fact]
    public async Task 같은_내용을_반복해_기록하지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "반복기록-PC");

        await ReportAsync(device, true);
        await ReportAsync(device, true);
        await ReportAsync(device, true);

        var count = await _server.WithDbAsync(db => db.DeviceEvents
            .CountAsync(e => e.DeviceId == device.DeviceId && e.Category == "보안"));

        // 매 연락마다 남기면 기록이 이것으로만 채워진다.
        Assert.Equal(1, count);
    }

    [Fact]
    public async Task 권한을_낮추면_표시가_사라진다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "권한낮춤-PC");

        await ReportAsync(device, true);
        Assert.True((await ReadDeviceAsync(device.DeviceId)).LastUserIsAdministrator);

        // 관리자가 계정 권한을 낮춘 뒤 다시 연락해 온 상황.
        await ReportAsync(device, false);

        Assert.False((await ReadDeviceAsync(device.DeviceId)).LastUserIsAdministrator);
    }

    [Fact]
    public async Task 낮췄다_다시_올리면_또_기록된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "권한재상승-PC");

        await ReportAsync(device, true);
        await ReportAsync(device, false);
        await ReportAsync(device, true);

        var count = await _server.WithDbAsync(db => db.DeviceEvents
            .CountAsync(e => e.DeviceId == device.DeviceId && e.Category == "보안"));

        // 낮췄다가 몰래 다시 올린 경우를 놓치면 안 된다.
        Assert.Equal(2, count);
    }

    [Fact]
    public async Task 보고하지_않으면_이전_값을_지우지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "무보고-PC");

        await ReportAsync(device, true);

        // 옛 버전 클라이언트처럼 이 값을 보내지 않는 경우.
        await device.HeartbeatAsync();

        var saved = await ReadDeviceAsync(device.DeviceId);
        Assert.True(saved.LastUserIsAdministrator);
    }

    [Fact]
    public async Task 화면_표시_판단이_맞다()
    {
        var admin = await DeviceClient.EnrollAsync(_server, "표시-관리자-PC");
        var normal = await DeviceClient.EnrollAsync(_server, "표시-일반-PC");

        await ReportAsync(admin, true);
        await ReportAsync(normal, false);

        var adminView = DeviceView.From(await ReadDeviceAsync(admin.DeviceId), 5);
        var normalView = DeviceView.From(await ReadDeviceAsync(normal.DeviceId), 5);

        Assert.True(adminView.UserCanBypass);
        Assert.False(normalView.UserCanBypass);
    }
}
