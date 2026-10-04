using System.Runtime.Versioning;
using System.Security.Cryptography.X509Certificates;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>
/// ✍🛡 **「확인되지 않은 게시자」 경고를 없앤다.**
///
///  왜 그 경고가 뜨는가:
///    Windows 는 **누가 만든 프로그램인지** 모르면 「Windows 의 PC 보호」를 띄운다.
///    우리는 사내에서 만들어 쓰는 프로그램이라 바깥 인증 기관의 보증서가 없다.
///    (그 보증서는 해마다 돈이 들고, 그래도 처음에는 「평판이 없다」고 또 뜬다.)
///
///  ⭐ 사내에서는 더 나은 길이 있다 — **우리 인증서를 이 회사 PC 들이 믿게** 하면 된다.
///    ①우리 손으로 인증서를 하나 만들고(build/인증서-만들기.ps1)
///    ②그 인증서로 설치 파일에 서명하고
///    ③설치할 때 **그 인증서를 이 PC 의 믿는 목록에 넣는다** ← 이 파일이 하는 일
///    그러면 그다음부터 그 인증서로 서명한 것은 **경고 없이** 돈다. 자동 업데이트도 조용하다.
///
///  ⚠⚠⚠ **이것은 그 열쇠를 가진 사람을 믿겠다는 뜻이다.**
///    열쇠(.pfx)가 새면, 그것으로 서명한 **아무 프로그램이나** 이 회사 PC 들이 믿게 된다.
///    그래서 열쇠는 저장소에 넣지 않고 담당자 PC 와 깃허브 비밀값에만 둔다.
///    (저장소에 함께 두는 것은 **공개용 인증서(.cer)** 뿐이다 — 이것으로는 서명하지 못한다.)
///
///  ⚠ 못 해도 설치는 계속한다. 그때는 예전처럼 [추가 정보] → [실행] 을 한 번 누르면 된다.
/// </summary>
[SupportedOSPlatform("windows")]
public static class CertificateTrust
{
    /// <summary>설치 파일 안에 함께 들어 있는 공개용 인증서 이름.</summary>
    public const string FileName = "hanil-code-signing.cer";

    /// <summary>
    /// 인증서를 이 PC 가 믿도록 등록한다.
    ///
    /// 두 곳에 넣는다:
    ///   Root            — 「이 인증서를 믿는다」
    ///   TrustedPublisher — 「이 게시자가 만든 프로그램은 물어보지 않는다」
    /// 둘 다 넣어야 경고가 조용해진다.
    /// </summary>
    public static bool Install(string certificatePath, out string error)
    {
        error = string.Empty;

        try
        {
            if (!File.Exists(certificatePath))
            {
                error = "인증서 파일이 없습니다.";
                return false;
            }

            //  ⚠ 공개용(.cer)이라 비밀 열쇠가 들어 있지 않다 — 이것으로는 서명할 수 없다.
            //  ⚠ .NET 8 이라 생성자를 쓴다(X509CertificateLoader 는 .NET 9 부터다).
            using var certificate = new X509Certificate2(certificatePath);

            var installed = false;
            installed |= AddTo(StoreName.Root, certificate);
            installed |= AddTo(StoreName.TrustedPublisher, certificate);

            if (!installed)
            {
                error = "인증서를 등록하지 못했습니다.";
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }

    /// <summary>이 PC 가 이미 그 인증서를 믿고 있는지.</summary>
    public static bool IsInstalled(string certificatePath)
    {
        try
        {
            if (!File.Exists(certificatePath)) return false;

            using var certificate = new X509Certificate2(certificatePath);
            using var store = new X509Store(StoreName.Root, StoreLocation.LocalMachine);

            store.Open(OpenFlags.ReadOnly);

            return Contains(store.Certificates, certificate);
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>같은 인증서가 이미 들어 있는지. ⚠ 지문으로만 본다 — 이름은 같아도 다른 인증서일 수 있다.</summary>
    private static bool Contains(X509Certificate2Collection collection, X509Certificate2 certificate)
    {
        foreach (var item in collection)
        {
            if (string.Equals(item.Thumbprint, certificate.Thumbprint, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    private static bool AddTo(StoreName name, X509Certificate2 certificate)
    {
        try
        {
            using var store = new X509Store(name, StoreLocation.LocalMachine);

            store.Open(OpenFlags.ReadWrite);

            //  ⚠ 이미 있으면 또 넣지 않는다 — 같은 인증서가 여러 줄로 쌓이면 보기 흉하다.
            if (!Contains(store.Certificates, certificate))
                store.Add(certificate);

            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }
}
