using System.Security.Cryptography;
using Hanil.TimeGuard.Core.Config;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Data;

/// <summary>서버 전역 설정과 장비 토큰을 다룬다.</summary>
public sealed class SettingsService
{
    internal const string EnrollmentKeyName = "EnrollmentKey";
    internal const string OfflineMinutesName = "OfflineAfterMinutes";
    internal const string AdminAddressesName = "AdminAllowedAddresses";

    private readonly GuardDbContext _db;

    public SettingsService(GuardDbContext db) => _db = db;

    public async Task<string> GetAsync(string key, string fallback, CancellationToken token = default)
    {
        var setting = await _db.Settings.FirstOrDefaultAsync(s => s.Key == key, token);
        return setting?.Value ?? fallback;
    }

    public async Task SetAsync(string key, string value, CancellationToken token = default)
    {
        var setting = await _db.Settings.FirstOrDefaultAsync(s => s.Key == key, token);

        if (setting is null)
            _db.Settings.Add(new ServerSetting { Key = key, Value = value });
        else
            setting.Value = value;

        await _db.SaveChangesAsync(token);
    }

    /// <summary>등록 키를 읽는다. 없으면 새로 만들어 저장한다.</summary>
    public async Task<string> GetOrCreateEnrollmentKeyAsync(CancellationToken token = default)
    {
        var existing = await _db.Settings.FirstOrDefaultAsync(s => s.Key == EnrollmentKeyName, token);
        if (existing is not null && !string.IsNullOrWhiteSpace(existing.Value)) return existing.Value;

        var key = GenerateReadableKey();

        if (existing is null)
            _db.Settings.Add(new ServerSetting { Key = EnrollmentKeyName, Value = key });
        else
            existing.Value = key;

        await _db.SaveChangesAsync(token);
        return key;
    }

    /// <summary>관리 화면을 열 수 있는 주소 목록. 비어 있으면 제한하지 않는다.</summary>
    public Task<string> GetAdminAddressesAsync(CancellationToken token = default) =>
        GetAsync(AdminAddressesName, string.Empty, token);

    /// <summary>하트비트가 이 시간 이상 없으면 연결이 끊긴 것으로 본다.</summary>
    public async Task<int> GetOfflineAfterMinutesAsync(CancellationToken token = default)
    {
        var raw = await GetAsync(OfflineMinutesName, "5", token);
        return int.TryParse(raw, out var minutes) && minutes > 0 ? minutes : 5;
    }

    /// <summary>사람이 받아 적기 쉬운 등록 키를 만든다. 헷갈리는 글자는 뺐다.</summary>
    internal static string GenerateReadableKey()
    {
        const string alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // I, O, 0, 1 제외
        var characters = new char[20];

        for (var i = 0; i < characters.Length; i++)
            characters[i] = alphabet[RandomNumberGenerator.GetInt32(alphabet.Length)];

        // 네 글자씩 끊어 읽기 쉽게 만든다.
        return string.Join('-',
            new string(characters, 0, 5),
            new string(characters, 5, 5),
            new string(characters, 10, 5),
            new string(characters, 15, 5));
    }

    /// <summary>장비 토큰을 새로 만든다. 원본은 한 번만 돌려주고 서버에는 해시만 남는다.</summary>
    internal static (string Token, string Hash) CreateDeviceToken()
    {
        var token = Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
                           .Replace('+', '-').Replace('/', '_').TrimEnd('=');

        return (token, HashToken(token));
    }

    /// <summary>
    /// 장비 토큰은 32바이트 난수라 사전 공격 대상이 아니므로 SHA-256 한 번이면 충분하다.
    /// (사람이 정하는 관리자 비밀번호는 PBKDF2 를 쓴다.)
    /// </summary>
    internal static string HashToken(string token) =>
        Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(token)));

    /// <summary>관리자 계정이 하나도 없으면 기본 계정을 만든다.</summary>
    public async Task<string?> EnsureAdminUserAsync(CancellationToken token = default)
    {
        if (await _db.AdminUsers.AnyAsync(token)) return null;

        var password = GenerateReadableKey()[..14]; // 첫 설치용 임시 비밀번호

        _db.AdminUsers.Add(new AdminUser
        {
            UserName = "admin",
            PasswordHash = PasswordHasher.Hash(password)
        });

        await _db.SaveChangesAsync(token);
        return password;
    }
}
