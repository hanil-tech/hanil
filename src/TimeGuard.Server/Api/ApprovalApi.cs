using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Api;

/// <summary>
/// 등록 키 없이 PC 를 등록하는 흐름.
///
/// 직원 PC 가 서버를 찾아 "저 여기 있습니다" 하고 알리면 승인 대기 목록에 올라간다.
/// 관리자가 서버 화면에서 승인해야 실제로 등록되고 시간표를 받아 간다.
/// 프린터를 연결할 때처럼, 받아 적을 것이 없다.
/// </summary>
public static class ApprovalApi
{
    /// <summary>승인 대기로 쌓아 둘 수 있는 최대 개수. 누군가 목록을 채워 못 쓰게 만드는 것을 막는다.</summary>
    private const int MaxPendingDevices = 200;

    public static void MapApprovalApi(this IEndpointRouteBuilder app)
    {
        app.MapPost(ServerRoutes.Announce, AnnounceAsync);
        app.MapPost(ServerRoutes.Claim, ClaimAsync);
    }

    // ---- 자기를 알린다 ----

    private static async Task<IResult> AnnounceAsync(
        AnnounceRequest request,
        HttpContext context,
        GuardDbContext db,
        ILogger<Program> logger,
        CancellationToken token)
    {
        if (string.IsNullOrWhiteSpace(request.MachineName))
            return Results.BadRequest(ApiError.From("PC 이름이 비어 있습니다."));

        if (string.IsNullOrWhiteSpace(request.ClientId) || request.ClientId.Length < 32)
            return Results.BadRequest(ApiError.From("PC 식별값이 올바르지 않습니다."));

        var clientHash = SettingsService.HashToken(request.ClientId);
        var fingerprint = ServerSettings.DescribeFingerprint(request.ClientId);

        var device = await db.Devices.FirstOrDefaultAsync(d => d.ClientIdHash == clientHash, token);

        if (device is null)
        {
            // 같은 PC 가 프로그램을 다시 깔았을 수 있다. 이름이 같으면 그 항목을 이어 쓴다.
            device = await db.Devices.FirstOrDefaultAsync(
                d => d.MachineName == request.MachineName && d.ClientIdHash == string.Empty, token);
        }

        if (device is null)
        {
            var pending = await db.Devices.CountAsync(d => d.Approval == ApprovalState.Pending, token);

            if (pending >= MaxPendingDevices)
            {
                logger.LogWarning("승인 대기 목록이 가득 차 새 PC 알림을 받지 않았습니다: {Machine}", request.MachineName);

                return Results.Json(
                    ApiError.From("승인 대기 목록이 가득 찼습니다. 관리자에게 문의해 주세요."),
                    statusCode: StatusCodes.Status429TooManyRequests);
            }

            device = new Device
            {
                MachineName = request.MachineName,
                DisplayName = request.MachineName,
                Approval = ApprovalState.Pending,
                AnnouncedAt = DateTimeOffset.Now
            };

            db.Devices.Add(device);

            db.DeviceEvents.Add(new DeviceEvent
            {
                DeviceId = device.Id,
                Category = "등록",
                Message = $"새 PC 가 발견되었습니다. 승인을 기다리는 중입니다. 사용자: {request.OsUser}"
            });

            logger.LogInformation("새 PC 가 자기를 알렸습니다: {Machine} ({User})",
                request.MachineName, request.OsUser);
        }

        device.ClientIdHash = clientHash;
        device.Fingerprint = fingerprint;
        device.MachineName = request.MachineName;
        device.AnnouncedFrom = DescribeAddress(context);
        device.AnnouncedAt ??= DateTimeOffset.Now;

        if (!string.IsNullOrWhiteSpace(request.OsUser)) device.LastUser = request.OsUser;
        if (string.IsNullOrWhiteSpace(device.DisplayName)) device.DisplayName = request.MachineName;

        await db.SaveChangesAsync(token);

        return Results.Ok(new AnnounceResponse
        {
            State = device.Approval.ToString(),
            Fingerprint = fingerprint,
            Message = DescribeState(device.Approval)
        });
    }

    // ---- 승인되었는지 확인하고 토큰을 받아 간다 ----

    private static async Task<IResult> ClaimAsync(
        ClaimRequest request,
        GuardDbContext db,
        ILogger<Program> logger,
        CancellationToken token)
    {
        if (string.IsNullOrWhiteSpace(request.ClientId))
            return Results.BadRequest(ApiError.From("PC 식별값이 비어 있습니다."));

        var clientHash = SettingsService.HashToken(request.ClientId);
        var device = await db.Devices.FirstOrDefaultAsync(d => d.ClientIdHash == clientHash, token);

        if (device is null)
        {
            // 관리자가 목록에서 지웠을 수 있다. 다시 알리도록 안내한다.
            return Results.Ok(new ClaimResponse
            {
                State = ApprovalStates.Pending,
                Message = "아직 서버에 알려지지 않았습니다. 잠시 뒤 다시 시도합니다."
            });
        }

        if (device.Approval == ApprovalState.Rejected)
        {
            return Results.Ok(new ClaimResponse
            {
                State = ApprovalStates.Rejected,
                Message = "관리자가 이 PC 의 등록을 거절했습니다."
            });
        }

        if (device.Approval != ApprovalState.Approved)
        {
            return Results.Ok(new ClaimResponse
            {
                State = ApprovalStates.Pending,
                Message = "관리자의 승인을 기다리는 중입니다."
            });
        }

        // 승인되었다. 토큰을 새로 발급한다.
        var (plainToken, hash) = SettingsService.CreateDeviceToken();

        device.TokenHash = hash;

        db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = device.Id,
            Category = "등록",
            Message = "승인 후 등록을 마쳤습니다."
        });

        await db.SaveChangesAsync(token);

        logger.LogInformation("승인된 PC 가 등록을 마쳤습니다: {Machine}", device.MachineName);

        return Results.Ok(new ClaimResponse
        {
            State = ApprovalStates.Approved,
            DeviceId = device.Id,
            Token = plainToken,
            DisplayName = device.DisplayName,
            Message = $"'{device.DisplayName}' 이름으로 등록되었습니다."
        });
    }

    // ---- 공통 ----

    private static string DescribeState(ApprovalState state) => state switch
    {
        ApprovalState.Pending => "관리자의 승인을 기다리는 중입니다.",
        ApprovalState.Approved => "이미 승인된 PC 입니다.",
        ApprovalState.Rejected => "관리자가 등록을 거절했습니다.",
        _ => string.Empty
    };

    private static string DescribeAddress(HttpContext context)
    {
        var address = context.Connection.RemoteIpAddress;
        if (address is null) return string.Empty;

        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();
        return address.ToString();
    }
}
