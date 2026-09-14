using System.Diagnostics;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Runtime.Versioning;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>방화벽 규칙과 통신 암호화 준비.</summary>
[SupportedOSPlatform("windows")]
public static class NetworkSetup
{
    /// <summary>
    /// 사내망에서만 들어올 수 있게 포트를 연다.
    /// 공용 네트워크(카페 와이파이 등)에서는 열리지 않는다.
    /// </summary>
    public static bool OpenPort(string ruleName, int port, string protocol, out string detail)
    {
        detail = string.Empty;

        // 같은 이름의 규칙이 남아 있으면 지우고 다시 만든다.
        Netsh($"advfirewall firewall delete rule name=\"{ruleName}\"");

        var result = Netsh(
            $"advfirewall firewall add rule name=\"{ruleName}\" dir=in action=allow " +
            $"protocol={protocol} localport={port} profile=domain,private");

        if (result.ExitCode != 0)
        {
            detail = result.Output;
            return false;
        }

        return true;
    }

    public static void ClosePort(string ruleName) =>
        Netsh($"advfirewall firewall delete rule name=\"{ruleName}\"");

    /// <summary>이 PC 의 사내망 주소를 찾는다. 설치 후 접속 주소를 안내하는 데 쓴다.</summary>
    public static string? FindLocalAddress()
    {
        try
        {
            foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (network.OperationalStatus != OperationalStatus.Up) continue;
                if (network.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;

                foreach (var address in network.GetIPProperties().UnicastAddresses)
                {
                    if (address.Address.AddressFamily != AddressFamily.InterNetwork) continue;

                    var text = address.Address.ToString();
                    if (text.StartsWith("169.254.", StringComparison.Ordinal)) continue;

                    return text;
                }
            }
        }
        catch (Exception)
        {
            // 주소를 못 찾아도 설치는 끝낼 수 있다.
        }

        return null;
    }

    /// <summary>이 PC 의 모든 이름과 주소. 인증서에 담아 어느 주소로 접속해도 맞게 한다.</summary>
    public static List<string> CollectHostNames()
    {
        var names = new List<string> { Environment.MachineName, "localhost" };

        var domain = Environment.GetEnvironmentVariable("USERDNSDOMAIN");
        if (!string.IsNullOrWhiteSpace(domain))
            names.Add($"{Environment.MachineName}.{domain}");

        try
        {
            foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (network.OperationalStatus != OperationalStatus.Up) continue;

                foreach (var address in network.GetIPProperties().UnicastAddresses)
                {
                    if (address.Address.AddressFamily != AddressFamily.InterNetwork) continue;

                    var text = address.Address.ToString();
                    if (text.StartsWith("169.254.", StringComparison.Ordinal)) continue;

                    names.Add(text);
                }
            }
        }
        catch (Exception)
        {
            // 찾은 것까지만 쓴다.
        }

        return names.Where(n => !string.IsNullOrWhiteSpace(n)).Distinct().ToList();
    }

    /// <summary>
    /// 사내용 인증서를 만든다.
    ///
    /// 공인 기관 인증서를 받기 어려운 사내 서버라 직접 만들어 쓴다.
    /// 직원 PC 는 처음 연결할 때 본 인증서를 기억해 두고, 이후 달라지면 연결을 끊는다.
    /// </summary>
    public static X509Certificate2 CreateServerCertificate(IEnumerable<string> hostNames)
    {
        using var key = RSA.Create(2048);

        var request = new CertificateRequest(
            "CN=HanilTimeGuardServer",
            key,
            HashAlgorithmName.SHA256,
            RSASignaturePadding.Pkcs1);

        request.CertificateExtensions.Add(
            new X509BasicConstraintsExtension(certificateAuthority: false, hasPathLengthConstraint: false, 0, critical: true));

        request.CertificateExtensions.Add(
            new X509KeyUsageExtension(
                X509KeyUsageFlags.DigitalSignature | X509KeyUsageFlags.KeyEncipherment,
                critical: true));

        request.CertificateExtensions.Add(
            new X509EnhancedKeyUsageExtension(
                new OidCollection { new("1.3.6.1.5.5.7.3.1") },   // 서버 인증
                critical: false));

        var alternativeNames = new SubjectAlternativeNameBuilder();

        foreach (var name in hostNames)
        {
            if (IPAddress.TryParse(name, out var address)) alternativeNames.AddIpAddress(address);
            else alternativeNames.AddDnsName(name);
        }

        request.CertificateExtensions.Add(alternativeNames.Build());

        return request.CreateSelfSigned(
            DateTimeOffset.Now.AddDays(-1),
            DateTimeOffset.Now.AddYears(10));
    }

    /// <summary>이 PC 가 이 인증서를 믿도록 등록한다. 서버 PC 에서는 경고가 뜨지 않게 된다.</summary>
    public static void TrustOnThisMachine(X509Certificate2 certificate)
    {
        try
        {
            using var store = new X509Store(StoreName.Root, StoreLocation.LocalMachine);
            store.Open(OpenFlags.ReadWrite);

            var already = store.Certificates
                .Cast<X509Certificate2>()
                .Any(c => c.Thumbprint == certificate.Thumbprint);

            if (!already) store.Add(certificate);

            store.Close();
        }
        catch (Exception)
        {
            // 믿음 등록에 실패해도 통신은 암호화된다. 브라우저 경고만 뜬다.
        }
    }

    private static (int ExitCode, string Output) Netsh(string arguments)
    {
        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "netsh.exe",
                Arguments = arguments,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            if (process is null) return (-1, "netsh.exe 를 실행하지 못했습니다.");

            var output = process.StandardOutput.ReadToEnd() + process.StandardError.ReadToEnd();
            process.WaitForExit(30000);

            return (process.ExitCode, output.Trim());
        }
        catch (Exception ex)
        {
            return (-1, ex.Message);
        }
    }
}
