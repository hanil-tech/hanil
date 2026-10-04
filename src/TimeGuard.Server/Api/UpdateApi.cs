using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;

namespace Hanil.TimeGuard.Server.Api;

/// <summary>
/// 직원 PC 에 **새 판을 나눠 주는** API.
///
/// 왜 서버가 나눠 주는가:
///   ① 직원 PC 는 이미 서버와 이야기하고 있다 — 새 길을 만들 까닭이 없다.
///   ② 사내망 안이라 인터넷이 끊겨도 된다.
///   ③ **관리 서버 한 대만** 새로 깔면 직원 PC 들이 알아서 따라온다.
///      예전에는 PC 열 대를 돌며 설치 파일을 하나씩 실행해야 했다.
///
/// ⚠⚠ **승인된 PC 에게만** 준다(장비 토큰 확인). 설치 파일은 관리자 권한으로 실행되는 것이라
///   아무에게나 내줄 것이 아니다 — 안을 뜯어보면 사내 구조가 드러나기도 한다.
/// </summary>
public static class UpdateApi
{
    public static void MapUpdateApi(this IEndpointRouteBuilder app)
    {
        app.MapGet(ServerRoutes.Update, DescribeAsync);
        app.MapGet(ServerRoutes.UpdateFile, DownloadAsync);
    }

    /// <summary>나눠 줄 새 판이 있는지 알려 준다.</summary>
    private static async Task<IResult> DescribeAsync(
        HttpContext context, GuardDbContext db, UpdatePackage package, CancellationToken token)
    {
        var device = await DeviceApi.AuthenticateAsync(context, db, token);
        if (device is null) return DeviceApi.Unauthorized();
        if (device.Approval != ApprovalState.Approved) return DeviceApi.NotApproved();

        return Results.Ok(package.Describe());
    }

    /// <summary>설치 파일을 내려 준다.</summary>
    private static async Task<IResult> DownloadAsync(
        HttpContext context, GuardDbContext db, UpdatePackage package, CancellationToken token)
    {
        var device = await DeviceApi.AuthenticateAsync(context, db, token);
        if (device is null) return DeviceApi.Unauthorized();
        if (device.Approval != ApprovalState.Approved) return DeviceApi.NotApproved();

        if (!package.Exists)
            return Results.Json(ApiError.From("서버에 나눠 줄 설치 파일이 없습니다."),
                statusCode: StatusCodes.Status404NotFound);

        //  ⚠ 파일을 통째로 메모리에 올리지 않는다 — 수십 MB 다.
        var stream = File.OpenRead(package.FilePath);
        return Results.File(stream, "application/octet-stream", "TimeGuard-Setup.exe");
    }
}
