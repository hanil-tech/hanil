using System.Net;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace Hanil.TimeGuard.Server.Tests;

/// <summary>
/// 관리 화면이 로그인 없이 열리지 않는지 확인한다.
/// 여기가 뚫리면 직원이 브라우저만으로 시간표를 바꿀 수 있게 된다.
/// </summary>
public class AdminPageTests : IClassFixture<ServerFixture>
{
    private readonly ServerFixture _server;

    public AdminPageTests(ServerFixture server) => _server = server;

    private HttpClient CreateClientWithoutRedirects() =>
        _server.CreateClient(new Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactoryClientOptions
        {
            AllowAutoRedirect = false
        });

    [Theory]
    [InlineData("/")]
    [InlineData("/Index")]
    [InlineData("/Policy")]
    [InlineData("/Requests")]
    [InlineData("/Events")]
    [InlineData("/Settings")]
    public async Task 로그인하지_않으면_관리_화면에_못_들어간다(string path)
    {
        var http = CreateClientWithoutRedirects();

        var response = await http.GetAsync(path);

        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
        Assert.Contains("/Login", response.Headers.Location?.OriginalString ?? string.Empty);
    }

    [Fact]
    public async Task 로그인하지_않으면_PC_상세도_못_본다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "비공개-PC");
        var http = CreateClientWithoutRedirects();

        var response = await http.GetAsync($"/Device/{device.DeviceId}");

        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
        Assert.Contains("/Login", response.Headers.Location?.OriginalString ?? string.Empty);
    }

    [Fact]
    public async Task 로그인_화면은_누구나_볼_수_있다()
    {
        var http = _server.CreateClient();

        var response = await http.GetAsync("/Login");

        response.EnsureSuccessStatusCode();

        var html = await response.Content.ReadAsStringAsync();
        Assert.Contains("한일 TimeGuard", html);
        Assert.Contains("비밀번호", html);
    }

    [Fact]
    public async Task 서버_생존_확인은_로그인_없이_가능하다()
    {
        var http = _server.CreateClient();

        var response = await http.GetAsync("/api/ping");

        response.EnsureSuccessStatusCode();
    }

    [Fact]
    public async Task 최초_관리자_계정이_만들어진다()
    {
        var user = await _server.WithDbAsync(db => db.AdminUsers.FirstAsync());

        Assert.Equal("admin", user.UserName);
        Assert.StartsWith("pbkdf2$", user.PasswordHash);
    }

    [Fact]
    public async Task 관리자_비밀번호는_평문으로_저장되지_않는다()
    {
        var user = await _server.WithDbAsync(db => db.AdminUsers.FirstAsync());

        // 해시가 실제로 검증 가능한 형태인지 확인한다.
        Assert.False(PasswordHasher.Verify("admin", user.PasswordHash));
        Assert.False(PasswordHasher.Verify(string.Empty, user.PasswordHash));
    }

    [Fact]
    public async Task 장비_토큰은_평문으로_저장되지_않는다()
    {
        var device = await DeviceClient.EnrollAsync(_server, "토큰보관-PC");

        var stored = await _server.WithDbAsync(db =>
            db.Devices.Where(d => d.Id == device.DeviceId).Select(d => d.TokenHash).FirstAsync());

        Assert.NotEqual(device.Token, stored);
        Assert.Equal(64, stored.Length); // SHA-256 을 16진수로 적으면 64자
    }

    [Fact]
    public async Task 등록_키는_받아_적기_쉬운_형태다()
    {
        var key = await _server.GetEnrollmentKeyAsync();

        Assert.Equal(23, key.Length);          // 5자 네 묶음 + 하이픈 3개
        Assert.Equal(3, key.Count(c => c == '-'));
        Assert.DoesNotContain('O', key);       // 0 과 헷갈리는 글자는 빼 두었다
        Assert.DoesNotContain('I', key);
    }
}
