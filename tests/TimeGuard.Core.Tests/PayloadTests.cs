using System.IO.Compression;
using System.Reflection;
using System.Reflection.Emit;
using System.Text;
using Hanil.TimeGuard.SetupKit;
using Xunit;

namespace Hanil.TimeGuard.Core.Tests;

/// <summary>
/// 설치 프로그램이 자기 안에 든 파일을 푸는 부분.
///
/// 여기가 잘못되면 설치가 통째로 안 되므로, 실제 zip 을 만들어 확인한다.
/// 리소스를 품은 어셈블리를 흉내 내기 어려워 Stream 을 직접 넘기는 방식으로 시험한다.
/// </summary>
public class PayloadTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "timeguard-payload-" + Guid.NewGuid().ToString("N"));

    public PayloadTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (Exception) { }
        GC.SuppressFinalize(this);
    }

    private MemoryStream BuildZip(params (string Path, string Content)[] entries)
    {
        var stream = new MemoryStream();

        using (var archive = new ZipArchive(stream, ZipArchiveMode.Create, leaveOpen: true))
        {
            foreach (var (path, content) in entries)
            {
                var entry = archive.CreateEntry(path);
                using var writer = new StreamWriter(entry.Open(), Encoding.UTF8);
                writer.Write(content);
            }
        }

        stream.Position = 0;
        return stream;
    }

    [Fact]
    public void 파일을_그대로_푼다()
    {
        using var zip = BuildZip(("TimeGuard.Service.exe", "서비스"), ("appsettings.json", "{}"));
        var target = Path.Combine(_root, "install");

        Assert.True(Payload.Extract(zip, target, out var detail), detail);

        Assert.Equal("서비스", File.ReadAllText(Path.Combine(target, "TimeGuard.Service.exe")));
        Assert.Equal("{}", File.ReadAllText(Path.Combine(target, "appsettings.json")));
    }

    [Fact]
    public void 하위_폴더도_만든다()
    {
        using var zip = BuildZip(("wwwroot/site.css", "body{}"));
        var target = Path.Combine(_root, "install");

        Assert.True(Payload.Extract(zip, target, out _));

        Assert.Equal("body{}", File.ReadAllText(Path.Combine(target, "wwwroot", "site.css")));
    }

    [Fact]
    public void 다시_설치하면_덮어쓴다()
    {
        var target = Path.Combine(_root, "install");
        Directory.CreateDirectory(target);
        File.WriteAllText(Path.Combine(target, "TimeGuard.Service.exe"), "옛날 것");

        using var zip = BuildZip(("TimeGuard.Service.exe", "새 것"));

        Assert.True(Payload.Extract(zip, target, out _));
        Assert.Equal("새 것", File.ReadAllText(Path.Combine(target, "TimeGuard.Service.exe")));
    }

    [Fact]
    public void 설치_폴더_밖으로는_풀지_않는다()
    {
        // 묶음이 조작돼 "../" 가 들어와도 다른 폴더를 건드리면 안 된다.
        using var zip = BuildZip(("../밖에다쓰기.txt", "위험"), ("안전.txt", "정상"));

        var target = Path.Combine(_root, "install");

        Assert.True(Payload.Extract(zip, target, out _));

        Assert.False(File.Exists(Path.Combine(_root, "밖에다쓰기.txt")));
        Assert.True(File.Exists(Path.Combine(target, "안전.txt")));
    }

    [Fact]
    public void 한글_이름도_제대로_푼다()
    {
        // 배포본은 영문 이름만 쓰지만, 혹시 섞여 들어와도 깨지지 않아야 한다.
        using var zip = BuildZip(("설치안내.txt", "안내"));
        var target = Path.Combine(_root, "install");

        Assert.True(Payload.Extract(zip, target, out _));
        Assert.Equal("안내", File.ReadAllText(Path.Combine(target, "설치안내.txt")));
    }

    [Fact]
    public void 묶음이_없으면_실패를_알린다()
    {
        var assembly = Assembly.GetExecutingAssembly();

        Assert.False(Payload.IsEmbedded(assembly));
        Assert.Equal(0, Payload.Count(assembly));
        Assert.False(Payload.Extract(assembly, Path.Combine(_root, "install"), out var detail));
        Assert.NotEmpty(detail);
    }
}
