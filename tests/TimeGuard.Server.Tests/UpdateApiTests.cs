using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Api;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 💿 새 판 나눠 주기.
///
/// 여기가 뚫리면 **아무나 설치 파일을 받아 갈 수 있고**, 지문을 틀리게 주면
/// 직원 PC 가 **엉뚱한 프로그램을 관리자 권한으로 설치**하게 된다. 그래서 꼼꼼히 본다.
/// </summary>
public class UpdateApiTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public UpdateApiTests(ServerFixture server) => _server = server;

    private UpdatePackage Package => _server.Services.GetRequiredService<UpdatePackage>();

    /// <summary>나눠 줄 파일을 하나 놓아 둔다. 내용은 아무래도 좋다 — 지문만 맞으면 된다.</summary>
    private string PlacePackage(string version, string content)
    {
        var package = Package;

        Directory.CreateDirectory(package.Folder);
        File.WriteAllText(package.FilePath, content);
        File.WriteAllText(package.VersionPath, version);

        return Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(content)));
    }

    private void RemovePackage()
    {
        if (File.Exists(Package.FilePath)) File.Delete(Package.FilePath);
        if (File.Exists(Package.VersionPath)) File.Delete(Package.VersionPath);
    }

    [Fact]
    public async Task 토큰이_없으면_내주지_않는다()
    {
        var http = _server.CreateClient();

        var info = await http.GetAsync(ServerRoutes.Update);
        var file = await http.GetAsync(ServerRoutes.UpdateFile);

        Assert.Equal(HttpStatusCode.Unauthorized, info.StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, file.StatusCode);
    }

    [Fact]
    public async Task 승인되지_않은_PC에는_내주지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "승인전-PC");

        //  ⚠ 승인을 거둬들인 PC 가 그대로 받아 가면 안 된다.
        await _server.WithDbAsync(async db =>
        {
            var row = await db.Devices.FirstAsync(d => d.MachineName == "승인전-PC");
            row.Approval = ApprovalState.Pending;
            await db.SaveChangesAsync();
        });

        var response = await device.GetAsync(ServerRoutes.Update);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task 나눠_줄_파일이_없으면_없다고_답한다()
    {
        RemovePackage();

        var device = await DeviceClient.EnrollAsync(_server, "새판없음-PC");
        var response = await device.GetAsync(ServerRoutes.Update);

        response.EnsureSuccessStatusCode();

        var info = await response.Content.ReadFromJsonAsync<UpdateInfo>(IpcJson.Options);

        //  ⚠ 404 가 아니라 「없다」는 답이다 — 없는 것은 고장이 아니라 흔한 상태다.
        Assert.False(info!.Available);
    }

    [Fact]
    public async Task 파일을_두면_판_번호와_지문을_알려_준다()
    {
        var expected = PlacePackage("9.9.9", "이것이 새 판 설치 파일이라고 치자");

        var device = await DeviceClient.EnrollAsync(_server, "새판있음-PC");
        var response = await device.GetAsync(ServerRoutes.Update);

        response.EnsureSuccessStatusCode();

        var info = await response.Content.ReadFromJsonAsync<UpdateInfo>(IpcJson.Options);

        Assert.True(info!.Available);
        Assert.Equal("9.9.9", info.Version);
        Assert.Equal(expected, info.Sha256);

        RemovePackage();
    }

    [Fact]
    public async Task 받은_파일의_지문이_알려_준_것과_같다()
    {
        var expected = PlacePackage("9.9.9", "받아 보고 지문을 맞춰 본다");

        var device = await DeviceClient.EnrollAsync(_server, "내려받기-PC");
        var response = await device.GetAsync(ServerRoutes.UpdateFile);

        response.EnsureSuccessStatusCode();

        var bytes = await response.Content.ReadAsByteArrayAsync();

        //  ⭐⭐ 이것이 맞지 않으면 직원 PC 는 받은 파일을 **실행하지 않는다**.
        Assert.Equal(expected, Convert.ToHexString(SHA256.HashData(bytes)));

        RemovePackage();
    }

    [Fact]
    public void 파일이_바뀌면_지문도_다시_센다()
    {
        //  ⚠⚠ 지문을 기억해 두고 쓰는데, **새 판을 덮어썼는데도 옛 지문을 주면**
        //    직원 PC 는 받은 파일을 「바뀌었다」고 보고 버린다 — 영영 업데이트가 안 된다.
        var first = PlacePackage("1.0.0", "첫 번째");
        var before = Package.Describe();

        //  ⚠ 같은 초에 덮어쓰면 수정 시각이 안 바뀔 수 있다 — 일부러 뒤로 돌려 둔다.
        File.WriteAllText(Package.FilePath, "두 번째");
        File.SetLastWriteTimeUtc(Package.FilePath, DateTime.UtcNow.AddSeconds(1));

        var after = Package.Describe();

        Assert.Equal(first, before.Sha256);
        Assert.NotEqual(before.Sha256, after.Sha256);

        RemovePackage();
    }
}
