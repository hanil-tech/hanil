using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Server;
using Hanil.TimeGuard.Server.Api;
using Hanil.TimeGuard.Server.Data;
using Hanil.TimeGuard.Server.Security;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Hosting.WindowsServices;

// Windows 서비스로 실행하면 작업 디렉터리가 System32 가 되므로 실행 파일 위치를 기준으로 삼아야 한다.
// 반대로 개발 중 dotnet run 으로 띄울 때는 프로젝트 폴더가 기준이어야 wwwroot 를 찾을 수 있다.
var builder = WebApplication.CreateBuilder(new WebApplicationOptions
{
    Args = args,
    ContentRootPath = WindowsServiceHelpers.IsWindowsService() ? AppContext.BaseDirectory : null
});

// 서비스로 등록해 실행하든 콘솔에서 직접 실행하든 같은 코드가 동작한다.
builder.Services.AddWindowsService(options => options.ServiceName = "HanilTimeGuardServer");

// --- 데이터베이스 ---
// SQLite 라 별도 DB 설치가 필요 없다. 파일 하나에 모든 자료가 들어간다.
var dataDirectory = builder.Configuration["DataDirectory"]
                    ?? Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                        "HanilTimeGuardServer");

Directory.CreateDirectory(dataDirectory);
var databasePath = Path.Combine(dataDirectory, "timeguard.db");

builder.Services.AddDbContext<GuardDbContext>(options =>
    options.UseSqlite($"Data Source={databasePath}"));

// 클라이언트 API 의 JSON 형식을 IPC/설정 파일과 똑같이 맞춘다.
// 이렇게 하지 않으면 열거형이 숫자로, 시간이 "09:00:00" 으로 나가 형식이 갈린다.
builder.Services.ConfigureHttpJsonOptions(options => IpcJson.ApplyTo(options.SerializerOptions));

builder.Services.AddScoped<PolicyService>();
builder.Services.AddScoped<SettingsService>();

// 로그인 대입을 막는다. 서버 하나에서만 쓰므로 메모리에 두면 충분하다.
builder.Services.AddSingleton<LoginThrottle>();

// 관리 화면을 볼 수 있는 위치. 웹 화면에서 바꿀 수 있도록 설정을 객체에 담아 둔다.
builder.Services.AddSingleton<AdminAccessPolicy>();

// --- 인증 ---
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.LoginPath = "/Login";
        options.LogoutPath = "/Logout";
        options.AccessDeniedPath = "/Login";
        options.ExpireTimeSpan = TimeSpan.FromHours(8);
        options.SlidingExpiration = true;
        options.Cookie.Name = "HanilTimeGuard.Admin";
        options.Cookie.HttpOnly = true;
        options.Cookie.SameSite = SameSiteMode.Lax;
    });

builder.Services.AddAuthorization();

// 관리자 화면은 로그인해야 볼 수 있고, 클라이언트 API 는 장비 토큰으로 따로 확인한다.
builder.Services.AddRazorPages(options =>
{
    options.Conventions.AuthorizeFolder("/");
    options.Conventions.AllowAnonymousToPage("/Login");
});

builder.Services.AddAntiforgery();

// 사내망에서 이 서버를 찾을 수 있게 한다. 직원 PC 설치 때 주소를 적지 않아도 된다.
builder.Services.AddHostedService<DiscoveryResponder>();

// Razor 는 기본적으로 한글을 &#xC0DD; 같은 형태로 바꿔 내보낸다.
// 문서가 두 배 가까이 커지고 사람이 읽기도 어려우므로 한글을 그대로 내보내게 한다.
// (HTML 특수문자 이스케이프는 그대로 유지되므로 안전하다.)
builder.Services.AddSingleton<System.Text.Encodings.Web.HtmlEncoder>(
    System.Text.Encodings.Web.HtmlEncoder.Create(
        System.Text.Unicode.UnicodeRanges.BasicLatin,
        System.Text.Unicode.UnicodeRanges.HangulSyllables,
        System.Text.Unicode.UnicodeRanges.HangulJamo,
        System.Text.Unicode.UnicodeRanges.HangulCompatibilityJamo,
        System.Text.Unicode.UnicodeRanges.CjkSymbolsandPunctuation));

var app = builder.Build();

// --- 최초 실행 준비 ---
await InitializeAsync(app);

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
}

app.UseMiddleware<SecurityHeadersMiddleware>();
app.UseMiddleware<AdminNetworkMiddleware>();

app.UseStaticFiles();
app.UseRouting();
app.UseAuthentication();
app.UseAuthorization();

app.MapRazorPages();
app.MapDeviceApi();

// 서버가 살아 있는지 확인하는 용도. 로그인 없이 접근할 수 있다.
app.MapGet("/api/ping", () => Results.Ok(new { ok = true, time = DateTimeOffset.Now }));

app.Run();

static async Task InitializeAsync(WebApplication app)
{
    using var scope = app.Services.CreateScope();

    var db = scope.ServiceProvider.GetRequiredService<GuardDbContext>();
    var settings = scope.ServiceProvider.GetRequiredService<SettingsService>();
    var policies = scope.ServiceProvider.GetRequiredService<PolicyService>();
    var logger = scope.ServiceProvider.GetRequiredService<ILogger<Program>>();

    await db.Database.EnsureCreatedAsync();
    await policies.GetDefaultPolicyAsync();

    // 관리 화면 접근 제한을 불러와 적용한다.
    var policy = app.Services.GetRequiredService<AdminAccessPolicy>();
    var addresses = await settings.GetAdminAddressesAsync();
    policy.Update(addresses);

    logger.LogInformation(policy.Enabled
        ? "관리 화면은 지정된 주소에서만 열립니다: {Addresses}"
        : "관리 화면 접근 주소가 제한되어 있지 않습니다. [설정] 화면에서 제한할 수 있습니다.", addresses);

    var enrollmentKey = await settings.GetOrCreateEnrollmentKeyAsync();
    var initialPassword = await settings.EnsureAdminUserAsync();

    if (initialPassword is not null)
    {
        // 첫 실행에서만 나온다. 관리자가 받아 적고 바로 바꾸도록 안내한다.
        logger.LogWarning("=======================================================");
        logger.LogWarning(" 한일 TimeGuard 서버 최초 설정");
        logger.LogWarning("   관리자 아이디   : admin");
        logger.LogWarning("   임시 비밀번호   : {Password}", initialPassword);
        logger.LogWarning("   클라이언트 등록 키: {Key}", enrollmentKey);
        logger.LogWarning("   로그인 후 반드시 비밀번호를 바꿔 주세요.");
        logger.LogWarning("=======================================================");

        // 콘솔에서 놓치더라도 볼 수 있게 파일로도 남긴다.
        var notePath = Path.Combine(
            Path.GetDirectoryName(db.Database.GetDbConnection().DataSource) ?? ".",
            "최초설정정보.txt");

        try
        {
            await File.WriteAllTextAsync(notePath, $"""
                한일 TimeGuard 서버 최초 설정 정보
                생성 시각: {DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss}

                  관리자 아이디    : admin
                  임시 비밀번호    : {initialPassword}
                  클라이언트 등록 키: {enrollmentKey}

                로그인 후 [설정] 에서 비밀번호를 반드시 바꾸고 이 파일은 삭제하십시오.
                """, System.Text.Encoding.UTF8);
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "최초 설정 정보를 파일로 남기지 못했습니다.");
        }
    }

    logger.LogInformation("데이터 파일: {Path}", db.Database.GetDbConnection().DataSource);
}

/// <summary>통합 테스트에서 이 클래스를 잡을 수 있게 공개한다.</summary>
public partial class Program { }
