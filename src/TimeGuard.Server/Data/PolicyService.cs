using System.Text.Json;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Data;

/// <summary>
/// 저장된 기본 정책과 PC 별 설정을 합쳐 클라이언트가 그대로 쓸 수 있는 형태로 만든다.
/// </summary>
public sealed class PolicyService
{
    private readonly GuardDbContext _db;

    public PolicyService(GuardDbContext db) => _db = db;

    /// <summary>기본 정책을 읽는다. 없으면 만들어 둔다.</summary>
    public async Task<DefaultPolicy> GetDefaultPolicyAsync(CancellationToken token = default)
    {
        var policy = await _db.DefaultPolicies.FirstOrDefaultAsync(token);
        if (policy is not null) return policy;

        policy = CreateInitialPolicy();
        _db.DefaultPolicies.Add(policy);
        await _db.SaveChangesAsync(token);

        return policy;
    }

    internal static DefaultPolicy CreateInitialPolicy() => new()
    {
        Id = 1,
        ScheduleJson = JsonSerializer.Serialize(WeeklySchedule.CreateDefault(), IpcJson.Options),
        WarningsJson = JsonSerializer.Serialize(new WarningSettings(), IpcJson.Options),
        Action = nameof(GuardAction.Shutdown),
        HolidaysJson = "[]",
        HolidayPolicy = nameof(Core.Config.HolidayPolicy.Blocked),
        ExemptUsersJson = "[]",
        UpdatedBy = "설치",
        Version = 1
    };

    /// <summary>
    /// 한 PC 에 실제로 적용될 설정을 만든다.
    /// 기본 정책을 바탕으로 PC 전용 시간표, 연장, 일시 중지를 덮어씌운다.
    /// </summary>
    public async Task<GuardConfig> BuildEffectiveConfigAsync(Device device, CancellationToken token = default)
    {
        var defaults = await GetDefaultPolicyAsync(token);

        var config = new GuardConfig
        {
            // 서버가 관리하므로 클라이언트 쪽 비밀번호는 쓰지 않는다.
            PasswordHash = string.Empty,
            Enabled = device.Enforced,
            Action = Enum.TryParse<GuardAction>(defaults.Action, out var action) ? action : GuardAction.Shutdown,
            Schedule = DeserializeSchedule(device.UsesDefaultPolicy ? defaults.ScheduleJson : device.CustomScheduleJson),
            Warnings = Deserialize<WarningSettings>(defaults.WarningsJson) ?? new WarningSettings(),
            Holidays = Deserialize<List<string>>(defaults.HolidaysJson) ?? new List<string>(),
            HolidayPolicy = Enum.TryParse<HolidayPolicy>(defaults.HolidayPolicy, out var holiday)
                ? holiday
                : Core.Config.HolidayPolicy.Blocked,
            ExemptUsers = Deserialize<List<string>>(defaults.ExemptUsersJson) ?? new List<string>(),
            // 저장은 UTC 로 하지만 클라이언트 화면에는 지역 시각으로 보여야 하므로 변환해 보낸다.
            ExtensionUntil = device.ExtensionUntil?.ToLocalTime(),
            SuspendedUntil = device.SuspendedUntil?.ToLocalTime(),
            LastModified = defaults.UpdatedAt,
            LastModifiedBy = defaults.UpdatedBy
        };

        return config;
    }

    /// <summary>
    /// 클라이언트가 받은 정책이 최신인지 판단할 때 쓰는 값.
    /// 기본 정책 버전과 PC 별 버전을 합친다.
    /// </summary>
    public async Task<string> BuildPolicyStampAsync(Device device, CancellationToken token = default)
    {
        var defaults = await GetDefaultPolicyAsync(token);
        return $"{defaults.Version}-{device.PolicyVersion}";
    }

    /// <summary>기본 정책이 바뀌었음을 알린다.</summary>
    public async Task BumpDefaultVersionAsync(string changedBy, CancellationToken token = default)
    {
        var policy = await GetDefaultPolicyAsync(token);
        policy.Version++;
        policy.UpdatedAt = DateTimeOffset.Now;
        policy.UpdatedBy = changedBy;
        await _db.SaveChangesAsync(token);
    }

    private static WeeklySchedule DeserializeSchedule(string? json)
    {
        if (string.IsNullOrWhiteSpace(json)) return WeeklySchedule.CreateDefault();

        try
        {
            return JsonSerializer.Deserialize<WeeklySchedule>(json, IpcJson.Options)
                   ?? WeeklySchedule.CreateDefault();
        }
        catch (JsonException)
        {
            // 저장된 내용이 깨졌다면 제한이 느슨한 쪽이 아니라 기본 시간표로 돌아간다.
            return WeeklySchedule.CreateDefault();
        }
    }

    private static T? Deserialize<T>(string? json)
    {
        if (string.IsNullOrWhiteSpace(json)) return default;

        try
        {
            return JsonSerializer.Deserialize<T>(json, IpcJson.Options);
        }
        catch (JsonException)
        {
            return default;
        }
    }
}
