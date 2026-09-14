using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 원격 접속 차단 설정이 서버에서 직원 PC 까지 제대로 전달되는지 확인한다.
///
/// 계정을 잠가도 PC 에 다른 계정이 있으면 그 계정으로 원격 접속해 쓸 수 있어,
/// 이 설정이 실제로 내려가는지가 중요하다.
/// </summary>
public class RemoteAccessPolicyTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public RemoteAccessPolicyTests(ServerFixture server) => _server = server;

    [Fact]
    public void 처음_설치하면_원격_차단은_꺼져_있다()
    {
        // 켜 둔 채로 설치되면 원격으로 일하던 곳이 갑자기 막힌다.
        // 관리자가 알고 켜도록 기본은 꺼 둔다.
        //
        // 다른 시험들이 공유 정책을 바꾸므로 여기서는 갓 만든 정책을 확인한다.
        var initial = PolicyService.CreateInitialPolicy();

        Assert.False(initial.BlockRemoteAccess);
    }

    [Fact]
    public async Task 서버에서_켜면_직원_PC_에_전달된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "원격차단-PC");
        var before = await device.HeartbeatAsync();

        await _server.WithDbAsync(async db =>
        {
            var policy = await db.DefaultPolicies.FirstAsync();
            policy.BlockRemoteAccess = true;
            policy.Version++;
            await db.SaveChangesAsync();
        });

        var after = await device.HeartbeatAsync(policyStamp: before.PolicyStamp);

        Assert.NotNull(after.Policy);
        Assert.True(after.Policy!.BlockRemoteAccess);
    }

    [Fact]
    public async Task 다시_끄면_그것도_전달된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "원격해제-PC");

        await _server.WithDbAsync(async db =>
        {
            var policy = await db.DefaultPolicies.FirstAsync();
            policy.BlockRemoteAccess = false;
            policy.Version++;
            await db.SaveChangesAsync();
        });

        var response = await device.HeartbeatAsync();

        Assert.False(response.Policy!.BlockRemoteAccess);
    }

    [Fact]
    public async Task 계정_잠금_조치가_전달된다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "계정잠금-PC");
        var before = await device.HeartbeatAsync();

        await _server.WithDbAsync(async db =>
        {
            var policy = await db.DefaultPolicies.FirstAsync();
            policy.Action = nameof(Core.Config.GuardAction.AccountLock);
            policy.Version++;
            await db.SaveChangesAsync();
        });

        var after = await device.HeartbeatAsync(policyStamp: before.PolicyStamp);

        Assert.NotNull(after.Policy);
        Assert.Equal(Core.Config.GuardAction.AccountLock, after.Policy!.Action);
    }

    [Fact]
    public async Task 제외_계정은_계정_잠금에서도_빠진다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "제외계정-PC");
        var before = await device.HeartbeatAsync();

        await _server.WithDbAsync(async db =>
        {
            var policy = await db.DefaultPolicies.FirstAsync();
            policy.Action = nameof(Core.Config.GuardAction.AccountLock);
            policy.ExemptUsersJson = "[\"admin\",\"사장님\"]";
            policy.Version++;
            await db.SaveChangesAsync();
        });

        var after = await device.HeartbeatAsync(policyStamp: before.PolicyStamp);

        // 이 목록이 제대로 내려가지 않으면 관리자 계정이 잠길 수 있다.
        Assert.Contains("admin", after.Policy!.ExemptUsers);
        Assert.Contains("사장님", after.Policy.ExemptUsers);
    }
}
