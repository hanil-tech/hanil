using Hanil.TimeGuard.Core.Server;
using Hanil.TimeGuard.Server.Data;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Api;

/// <summary>클라이언트(직원 PC)가 호출하는 API.</summary>
public static class DeviceApi
{
    /// <summary>한 번에 받아 주는 이벤트 개수. 잘못 만든 클라이언트가 서버를 밀어붙이지 못하게 막는다.</summary>
    private const int MaxEventsPerReport = 200;

    /// <summary>한 PC 가 동시에 올려 둘 수 있는 대기 중 요청 수.</summary>
    private const int MaxPendingRequestsPerDevice = 3;

    /// <summary>한 번의 하트비트로 전달할 처리 결과 개수.</summary>
    private const int MaxDecisionsPerHeartbeat = 5;

    public static void MapDeviceApi(this IEndpointRouteBuilder app)
    {
        app.MapPost(ServerRoutes.Enroll, EnrollAsync);
        app.MapPost(ServerRoutes.Heartbeat, HeartbeatAsync);
        app.MapPost(ServerRoutes.Events, ReportEventsAsync);
        app.MapPost(ServerRoutes.ExtensionRequests, CreateExtensionRequestAsync);
        app.MapGet(ServerRoutes.MyRequests, GetMyRequestsAsync);
    }

    // ---- 등록 ----

    private static async Task<IResult> EnrollAsync(
        EnrollRequest request,
        GuardDbContext db,
        SettingsService settings,
        ILogger<Program> logger,
        CancellationToken token)
    {
        if (string.IsNullOrWhiteSpace(request.MachineName))
            return Results.BadRequest(ApiError.From("PC 이름이 비어 있습니다."));

        var expectedKey = await settings.GetOrCreateEnrollmentKeyAsync(token);

        if (!FixedTimeEquals(request.EnrollmentKey?.Trim(), expectedKey))
        {
            logger.LogWarning("등록 키가 맞지 않아 거부했습니다. PC: {Machine}", request.MachineName);
            return Results.Json(ApiError.From("등록 키가 올바르지 않습니다."), statusCode: StatusCodes.Status401Unauthorized);
        }

        // 같은 PC 가 다시 등록하면 기존 항목을 재사용해 목록이 중복되지 않게 한다.
        Device? device = null;

        if (!string.IsNullOrWhiteSpace(request.ExistingDeviceId))
            device = await db.Devices.FirstOrDefaultAsync(d => d.Id == request.ExistingDeviceId, token);

        device ??= await db.Devices.FirstOrDefaultAsync(d => d.MachineName == request.MachineName, token);

        var (plainToken, hash) = SettingsService.CreateDeviceToken();

        if (device is null)
        {
            device = new Device
            {
                MachineName = request.MachineName,
                DisplayName = request.MachineName,
                LastUser = request.OsUser ?? string.Empty,
                TokenHash = hash
            };

            db.Devices.Add(device);
            logger.LogInformation("새 PC 를 등록했습니다: {Machine}", request.MachineName);
        }
        else
        {
            // 재설치 등으로 다시 등록하는 경우. 토큰만 갱신하고 설정은 유지한다.
            device.TokenHash = hash;
            device.MachineName = request.MachineName;
            device.LastUser = request.OsUser ?? device.LastUser;
            logger.LogInformation("기존 PC 가 다시 등록했습니다: {Machine}", request.MachineName);
        }

        db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = device.Id,
            Category = "등록",
            Message = $"클라이언트가 등록했습니다. 사용자: {request.OsUser}"
        });

        await db.SaveChangesAsync(token);

        return Results.Ok(new EnrollResponse
        {
            DeviceId = device.Id,
            Token = plainToken,
            DisplayName = device.DisplayName
        });
    }

    // ---- 하트비트 ----

    private static async Task<IResult> HeartbeatAsync(
        HeartbeatRequest request,
        HttpContext context,
        GuardDbContext db,
        PolicyService policies,
        CancellationToken token)
    {
        var device = await AuthenticateAsync(context, db, token);
        if (device is null) return Unauthorized();

        device.LastSeenAt = DateTimeOffset.Now;
        device.LastState = request.State ?? string.Empty;
        device.LastReason = request.Reason ?? string.Empty;

        if (!string.IsNullOrWhiteSpace(request.OsUser)) device.LastUser = request.OsUser;

        var stamp = await policies.BuildPolicyStampAsync(device, token);

        var response = new HeartbeatResponse
        {
            ServerTime = DateTimeOffset.Now,
            PolicyStamp = stamp,
            ExtensionUntil = device.ExtensionUntil?.ToLocalTime(),
            SuspendedUntil = device.SuspendedUntil?.ToLocalTime(),
            Enforced = device.Enforced,
            DisplayName = device.DisplayName
        };

        // 정책이 바뀌었을 때만 전체 내용을 보낸다.
        if (request.PolicyStamp != stamp)
            response.Policy = await policies.BuildEffectiveConfigAsync(device, token);

        // 아직 이 PC 에 전달하지 않은 처리 결과만 보낸다.
        // 보내고 나면 전달 시각을 남겨 같은 알림이 반복되지 않게 한다.
        var undelivered = await db.ExtensionRequests
            .Where(r => r.DeviceId == device.Id
                        && r.Status != RequestStatus.Pending
                        && r.NotifiedAt == null)
            .OrderBy(r => r.Id)
            .Take(MaxDecisionsPerHeartbeat)
            .ToListAsync(token);

        var now = DateTimeOffset.Now;

        response.Decisions = undelivered.Select(r => new RequestDecision
        {
            RequestId = r.Id,
            Status = r.Status.ToString(),
            GrantedMinutes = r.GrantedMinutes,
            GrantedUntil = r.GrantedUntil?.ToLocalTime(),
            Note = r.DecisionNote,
            DecidedAt = (r.DecidedAt ?? r.RequestedAt).ToLocalTime()
        }).ToList();

        foreach (var delivered in undelivered) delivered.NotifiedAt = now;

        await db.SaveChangesAsync(token);

        return Results.Ok(response);
    }

    // ---- 이벤트 보고 ----

    private static async Task<IResult> ReportEventsAsync(
        EventReport report,
        HttpContext context,
        GuardDbContext db,
        CancellationToken token)
    {
        var device = await AuthenticateAsync(context, db, token);
        if (device is null) return Unauthorized();

        var entries = report.Entries.Take(MaxEventsPerReport);

        foreach (var entry in entries)
        {
            db.DeviceEvents.Add(new DeviceEvent
            {
                DeviceId = device.Id,
                At = entry.At == default ? DateTimeOffset.Now : entry.At,
                Category = Trim(entry.Category, 40),
                Message = Trim(entry.Message, 500)
            });
        }

        await db.SaveChangesAsync(token);
        return Results.Ok();
    }

    // ---- 연장 요청 ----

    private static async Task<IResult> CreateExtensionRequestAsync(
        ExtensionRequestInput input,
        HttpContext context,
        GuardDbContext db,
        CancellationToken token)
    {
        var device = await AuthenticateAsync(context, db, token);
        if (device is null) return Unauthorized();

        if (input.Minutes <= 0 || input.Minutes > 12 * 60)
            return Results.BadRequest(ApiError.From("연장 요청은 1분에서 720분(12시간) 사이여야 합니다."));

        var pending = await db.ExtensionRequests
            .CountAsync(r => r.DeviceId == device.Id && r.Status == RequestStatus.Pending, token);

        if (pending >= MaxPendingRequestsPerDevice)
            return Results.BadRequest(ApiError.From("이미 처리 대기 중인 요청이 있습니다. 관리자의 처리를 기다려 주세요."));

        var request = new ExtensionRequest
        {
            DeviceId = device.Id,
            RequestedMinutes = input.Minutes,
            Reason = Trim(input.Reason, 300),
            RequestedBy = Trim(string.IsNullOrWhiteSpace(input.OsUser) ? device.LastUser : input.OsUser, 100)
        };

        db.ExtensionRequests.Add(request);

        db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = device.Id,
            Category = "요청",
            Message = $"{input.Minutes}분 연장을 요청했습니다. 사유: {request.Reason}"
        });

        await db.SaveChangesAsync(token);

        return Results.Ok(new ExtensionRequestCreated
        {
            RequestId = request.Id,
            Message = "연장 요청을 보냈습니다. 관리자가 승인하면 적용됩니다."
        });
    }

    private static async Task<IResult> GetMyRequestsAsync(
        HttpContext context,
        GuardDbContext db,
        CancellationToken token)
    {
        var device = await AuthenticateAsync(context, db, token);
        if (device is null) return Unauthorized();

        var requests = await db.ExtensionRequests
            .Where(r => r.DeviceId == device.Id)
            .OrderByDescending(r => r.RequestedAt)
            .Take(20)
            .Select(r => new RequestDecision
            {
                RequestId = r.Id,
                Status = r.Status.ToString(),
                GrantedMinutes = r.GrantedMinutes,
                GrantedUntil = r.GrantedUntil,
                Note = r.DecisionNote,
                DecidedAt = r.DecidedAt ?? r.RequestedAt
            })
            .ToListAsync(token);

        return Results.Ok(requests);
    }

    // ---- 공통 ----

    /// <summary>헤더의 장비 토큰으로 어느 PC 인지 알아낸다.</summary>
    private static async Task<Device?> AuthenticateAsync(HttpContext context, GuardDbContext db, CancellationToken token)
    {
        if (!context.Request.Headers.TryGetValue(ServerRoutes.TokenHeader, out var values))
            return null;

        var raw = values.ToString();
        if (string.IsNullOrWhiteSpace(raw)) return null;

        var hash = SettingsService.HashToken(raw);
        return await db.Devices.FirstOrDefaultAsync(d => d.TokenHash == hash, token);
    }

    private static IResult Unauthorized() =>
        Results.Json(ApiError.From("장비 인증에 실패했습니다. 다시 등록이 필요합니다."),
            statusCode: StatusCodes.Status401Unauthorized);

    private static string Trim(string? text, int max)
    {
        if (string.IsNullOrEmpty(text)) return string.Empty;
        return text.Length <= max ? text : text[..max];
    }

    /// <summary>등록 키 비교에서 길이나 응답 시간으로 값이 새어 나가지 않게 한다.</summary>
    private static bool FixedTimeEquals(string? left, string? right)
    {
        if (left is null || right is null) return false;

        var a = System.Text.Encoding.UTF8.GetBytes(left);
        var b = System.Text.Encoding.UTF8.GetBytes(right);

        return System.Security.Cryptography.CryptographicOperations.FixedTimeEquals(a, b);
    }
}
