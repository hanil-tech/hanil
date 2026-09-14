using System.Security.Cryptography;

namespace Hanil.TimeGuard.Core.Config;

/// <summary>
/// 관리자 비밀번호를 PBKDF2-SHA256 으로 저장/검증한다.
/// 저장 형식: "pbkdf2$&lt;iterations&gt;$&lt;salt-base64&gt;$&lt;hash-base64&gt;"
/// </summary>
public static class PasswordHasher
{
    private const int DefaultIterations = 210_000;
    private const int SaltSize = 16;
    private const int HashSize = 32;
    private const string Prefix = "pbkdf2";

    public static string Hash(string password, int iterations = DefaultIterations)
    {
        ArgumentException.ThrowIfNullOrEmpty(password);

        var salt = RandomNumberGenerator.GetBytes(SaltSize);
        var hash = Rfc2898DeriveBytes.Pbkdf2(password, salt, iterations, HashAlgorithmName.SHA256, HashSize);

        return string.Join('$', Prefix, iterations, Convert.ToBase64String(salt), Convert.ToBase64String(hash));
    }

    public static bool Verify(string password, string stored)
    {
        if (string.IsNullOrEmpty(password) || string.IsNullOrEmpty(stored)) return false;

        var parts = stored.Split('$');
        if (parts.Length != 4 || parts[0] != Prefix) return false;
        if (!int.TryParse(parts[1], out var iterations) || iterations <= 0) return false;

        byte[] salt, expected;
        try
        {
            salt = Convert.FromBase64String(parts[2]);
            expected = Convert.FromBase64String(parts[3]);
        }
        catch (FormatException)
        {
            return false;
        }

        if (salt.Length == 0 || expected.Length == 0) return false;

        var actual = Rfc2898DeriveBytes.Pbkdf2(password, salt, iterations, HashAlgorithmName.SHA256, expected.Length);
        return CryptographicOperations.FixedTimeEquals(actual, expected);
    }

    /// <summary>비밀번호가 운영에 쓸 만한 최소 조건을 갖췄는지 확인한다.</summary>
    public static bool IsAcceptable(string password, out string problem)
    {
        problem = string.Empty;

        if (string.IsNullOrWhiteSpace(password))
        {
            problem = "비밀번호를 입력해 주세요.";
            return false;
        }
        if (password.Length < 8)
        {
            problem = "비밀번호는 8자 이상이어야 합니다.";
            return false;
        }
        if (password.All(char.IsDigit))
        {
            problem = "숫자만으로는 설정할 수 없습니다. 문자를 섞어 주세요.";
            return false;
        }
        return true;
    }
}
