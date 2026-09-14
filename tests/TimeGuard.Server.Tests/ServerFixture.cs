using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Server.Data;
using Hanil.TimeGuard.Core.Server;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Net.Http.Json;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 테스트마다 빈 데이터베이스로 서버를 띄운다.
/// 실제 HTTP 파이프라인을 그대로 통과시키므로 라우팅과 인증까지 함께 검증된다.
/// </summary>
public sealed class ServerFixture : WebApplicationFactory<Program>
{
    private readonly string _dataDirectory =
        Path.Combine(Path.GetTempPath(), "timeguard-server-test-" + Guid.NewGuid().ToString("N"));

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        Directory.CreateDirectory(_dataDirectory);

        builder.UseSetting("DataDirectory", _dataDirectory);
        builder.UseEnvironment("Development");
    }

    /// <summary>서버가 만든 등록 키를 읽어 온다.</summary>
    public async Task<string> GetEnrollmentKeyAsync()
    {
        using var scope = Services.CreateScope();
        var settings = scope.ServiceProvider.GetRequiredService<SettingsService>();
        return await settings.GetOrCreateEnrollmentKeyAsync();
    }

    /// <summary>테스트에서 데이터베이스를 직접 살펴보거나 손볼 때 쓴다.</summary>
    public async Task<T> WithDbAsync<T>(Func<GuardDbContext, Task<T>> action)
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<GuardDbContext>();
        return await action(db);
    }

    public async Task WithDbAsync(Func<GuardDbContext, Task> action)
    {
        using var scope = Services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<GuardDbContext>();
        await action(db);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);

        if (!disposing) return;

        try
        {
            if (Directory.Exists(_dataDirectory)) Directory.Delete(_dataDirectory, recursive: true);
        }
        catch (IOException)
        {
            // 파일이 아직 잠겨 있어도 테스트 결과에는 영향이 없다.
        }
    }
}

/// <summary>테스트에서 클라이언트 API 를 호출하기 편하게 감싼 것.</summary>
public sealed class DeviceClient
{
    private readonly HttpClient _http;

    public string DeviceId { get; }
    public string Token { get; }

    private DeviceClient(HttpClient http, string deviceId, string token)
    {
        _http = http;
        DeviceId = deviceId;
        Token = token;
    }

    public static async Task<DeviceClient> EnrollAsync(
        ServerFixture fixture, string machineName, string osUser = "HANIL\\tester")
    {
        var http = fixture.CreateClient();
        var key = await fixture.GetEnrollmentKeyAsync();

        var response = await http.PostAsJsonAsync(ServerRoutes.Enroll, new Core.Server.EnrollRequest
        {
            MachineName = machineName,
            OsUser = osUser,
            EnrollmentKey = key
        }, IpcJson.Options);

        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<Core.Server.EnrollResponse>(IpcJson.Options);
        return new DeviceClient(http, result!.DeviceId, result.Token);
    }

    public async Task<HttpResponseMessage> PostAsync<T>(string route, T body)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, route)
        {
            Content = JsonContent.Create(body, options: IpcJson.Options)
        };

        request.Headers.Add(ServerRoutes.TokenHeader, Token);
        return await _http.SendAsync(request);
    }

    public async Task<Core.Server.HeartbeatResponse> HeartbeatAsync(
        string state = "Allowed", string? policyStamp = null, string reason = "")
    {
        var response = await PostAsync(ServerRoutes.Heartbeat, new Core.Server.HeartbeatRequest
        {
            State = state,
            Reason = reason,
            PolicyStamp = policyStamp,
            OsUser = "HANIL\\tester",
            ClientVersion = "테스트"
        });

        response.EnsureSuccessStatusCode();
        return (await response.Content.ReadFromJsonAsync<Core.Server.HeartbeatResponse>(IpcJson.Options))!;
    }
}
