using System.Security.Cryptography;
using Hanil.TimeGuard.Core.Server;

namespace Hanil.TimeGuard.Server.Api;

/// <summary>
/// 서버가 나눠 줄 **직원 PC 설치 파일**.
///
/// 어디에 두는가:
///   %ProgramData%\HanilTimeGuardServer\updates\TimeGuard-Setup.exe
///   관리 서버를 새로 설치하면 설치 프로그램이 이 자리에 새 파일을 놓는다.
///   그러면 직원 PC 들이 그것을 보고 알아서 따라온다 — **서버 한 대만 올리면 끝**이다.
///
/// ⚠ 파일이 없으면 「나눠 줄 것이 없다」고 답한다. 그것이 정상이고, 고장이 아니다.
///   자동 업데이트를 쓰고 싶지 않으면 이 파일만 지우면 된다.
/// </summary>
public sealed class UpdatePackage
{
    private readonly object _lock = new();

    /// <summary>파일이 안 바뀌었으면 지문을 다시 세지 않기 위해 기억해 둔다.</summary>
    private (long Length, DateTime WrittenUtc, UpdateInfo Info)? _cached;

    public UpdatePackage(string folder)
    {
        Folder = folder;
        FilePath = Path.Combine(folder, "TimeGuard-Setup.exe");
        VersionPath = Path.Combine(folder, "version.txt");
    }

    public string Folder { get; }
    public string FilePath { get; }
    public string VersionPath { get; }

    /// <summary>나눠 줄 파일이 있는지.</summary>
    public bool Exists => File.Exists(FilePath);

    /// <summary>
    /// 지금 나눠 줄 수 있는 것을 알려 준다.
    ///
    /// ⚠⚠ 지문(SHA-256)을 세는 데 수십 MB 를 읽는다. 직원 PC 가 여러 대면 그때마다 세게 된다 —
    ///   그래서 **파일이 바뀌지 않았으면 기억해 둔 값을 그대로** 준다.
    /// </summary>
    public UpdateInfo Describe()
    {
        try
        {
            if (!File.Exists(FilePath))
                return new UpdateInfo { Available = false, Message = "서버에 나눠 줄 설치 파일이 없습니다." };

            var file = new FileInfo(FilePath);

            lock (_lock)
            {
                if (_cached is { } cached &&
                    cached.Length == file.Length &&
                    cached.WrittenUtc == file.LastWriteTimeUtc)
                {
                    return cached.Info;
                }

                var info = new UpdateInfo
                {
                    Available = true,
                    Version = ReadVersion(),
                    Sha256 = Hash(FilePath),
                    Size = file.Length,
                    Message = "서버가 가지고 있는 설치 파일입니다."
                };

                _cached = (file.Length, file.LastWriteTimeUtc, info);
                return info;
            }
        }
        catch (Exception ex)
        {
            //  ⚠ 업데이트는 **못 해도 그만인 일**이다. 여기서 터뜨려 서버를 멈추게 하지 않는다.
            return new UpdateInfo { Available = false, Message = $"설치 파일을 읽지 못했습니다: {ex.Message}" };
        }
    }

    /// <summary>
    /// 판 번호를 읽는다.
    ///
    /// ⚠ `version.txt` 를 **먼저** 본다. 설치 프로그램이 파일을 놓을 때 함께 적어 두기 때문이다.
    ///   그것이 없으면 실행 파일에 박힌 판 번호를 본다(사람이 손으로 갖다 놓은 경우).
    /// </summary>
    private string ReadVersion()
    {
        try
        {
            if (File.Exists(VersionPath))
            {
                var text = File.ReadAllText(VersionPath).Trim();
                if (text.Length > 0) return text;
            }
        }
        catch (Exception) { /* 아래로 넘어간다 */ }

        try
        {
            var version = System.Diagnostics.FileVersionInfo.GetVersionInfo(FilePath).FileVersion;
            if (!string.IsNullOrWhiteSpace(version)) return version!;
        }
        catch (Exception) { /* 아래로 넘어간다 */ }

        return "0.0.0";
    }

    private static string Hash(string path)
    {
        using var stream = File.OpenRead(path);
        using var sha = SHA256.Create();
        return Convert.ToHexString(sha.ComputeHash(stream));
    }
}
