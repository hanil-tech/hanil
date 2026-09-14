using System.IO.Compression;
using System.Reflection;
using System.Runtime.Versioning;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>
/// 설치할 파일 묶음. 설치 프로그램 안에 통째로 들어 있다.
///
/// 이렇게 하는 이유:
///   폴더에 파일 수백 개를 같이 주면 어느 것을 눌러야 하는지 알기 어렵고,
///   메신저로 주고받다가 파일이 빠지기도 한다.
///   설치 파일 하나만 건네면 그런 일이 없다.
/// </summary>
[SupportedOSPlatform("windows")]
public static class Payload
{
    /// <summary>빌드할 때 넣어 두는 이름.</summary>
    public const string ResourceName = "TimeGuard.Payload.zip";

    /// <summary>설치할 파일이 이 프로그램 안에 들어 있는지.</summary>
    public static bool IsEmbedded(Assembly assembly) =>
        assembly.GetManifestResourceNames().Contains(ResourceName);

    /// <summary>안에 든 파일 수. 진행 상황을 보여 주는 데 쓴다.</summary>
    public static int Count(Assembly assembly)
    {
        try
        {
            using var stream = assembly.GetManifestResourceStream(ResourceName);
            if (stream is null) return 0;

            using var archive = new ZipArchive(stream, ZipArchiveMode.Read);
            return archive.Entries.Count(e => e.Name.Length > 0);
        }
        catch (Exception)
        {
            return 0;
        }
    }

    /// <summary>
    /// 안에 든 파일을 목적지 폴더에 푼다.
    /// 이미 있는 파일은 덮어쓴다. 갱신 설치가 되도록.
    /// </summary>
    public static bool Extract(Assembly assembly, string destination, out string detail)
    {
        detail = string.Empty;

        using var stream = assembly.GetManifestResourceStream(ResourceName);

        if (stream is null)
        {
            detail = "설치 파일 묶음을 찾을 수 없습니다.";
            return false;
        }

        return Extract(stream, destination, out detail);
    }

    /// <summary>묶음을 읽어 목적지 폴더에 푼다.</summary>
    public static bool Extract(Stream payload, string destination, out string detail)
    {
        detail = string.Empty;

        try
        {
            Directory.CreateDirectory(destination);

            // 비교 기준을 한 번만 만들어 둔다. 뒤에 구분자를 붙여야
            // "install" 과 "install-backup" 을 헷갈리지 않는다.
            var root = Path.GetFullPath(destination);
            if (!root.EndsWith(Path.DirectorySeparatorChar)) root += Path.DirectorySeparatorChar;

            using var archive = new ZipArchive(payload, ZipArchiveMode.Read);

            foreach (var entry in archive.Entries)
            {
                // 폴더 항목은 이름이 비어 있다.
                if (entry.Name.Length == 0) continue;

                var target = Path.GetFullPath(Path.Combine(destination, entry.FullName));

                // 묶음 안에 "../" 가 들어 있어도 설치 폴더 밖으로 나가지 못하게 막는다.
                if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase)) continue;

                var folder = Path.GetDirectoryName(target);
                if (!string.IsNullOrEmpty(folder)) Directory.CreateDirectory(folder);

                entry.ExtractToFile(target, overwrite: true);
            }

            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }
}
