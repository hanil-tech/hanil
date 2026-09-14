using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Text;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.Server;

/// <summary>사내망에서 찾아낸 관리 서버.</summary>
public sealed class DiscoveredServer
{
    /// <summary>접속 주소. 예: https://192.168.0.10:8443</summary>
    public string Url { get; set; } = string.Empty;

    /// <summary>서버가 설치된 PC 이름. 관리자가 맞는 서버인지 확인하는 데 쓴다.</summary>
    public string MachineName { get; set; } = string.Empty;

    /// <summary>서버 프로그램 버전.</summary>
    public string Version { get; set; } = string.Empty;

    /// <summary>응답이 실제로 온 주소.</summary>
    public string? RespondedFrom { get; set; }

    public override string ToString() => $"{Url} ({MachineName})";
}

/// <summary>
/// 사내망에서 관리 서버를 찾는다.
///
/// 직원 PC 마다 서버 IP 를 받아 적어 넣지 않아도 되도록,
/// 클라이언트가 "서버 계십니까" 하고 사내망에 물으면 서버가 자기 주소를 알려 준다.
/// </summary>
public static class ServerDiscovery
{
    /// <summary>찾기 신호를 주고받는 포트.</summary>
    public const int Port = 8765;

    /// <summary>클라이언트가 보내는 문의 문구. 엉뚱한 프로그램의 신호와 섞이지 않게 한다.</summary>
    public const string Question = "한일TimeGuard:서버계십니까?v1";

    /// <summary>서버 응답 앞에 붙는 표시.</summary>
    public const string AnswerPrefix = "한일TimeGuard:여기있습니다:";

    /// <summary>
    /// 사내망에 문의를 보내고 응답하는 서버들을 모은다.
    /// 서버가 없거나 방화벽에 막히면 빈 목록을 돌려준다.
    /// </summary>
    public static async Task<List<DiscoveredServer>> FindAsync(
        TimeSpan? timeout = null, CancellationToken token = default)
    {
        var waitFor = timeout ?? TimeSpan.FromSeconds(3);
        var found = new Dictionary<string, DiscoveredServer>(StringComparer.OrdinalIgnoreCase);

        using var client = new UdpClient();
        client.EnableBroadcast = true;

        try
        {
            client.Client.Bind(new IPEndPoint(IPAddress.Any, 0));
        }
        catch (SocketException)
        {
            return new List<DiscoveredServer>();
        }

        var question = Encoding.UTF8.GetBytes(Question);

        // 사내망 전체 브로드캐스트와, 각 랜카드가 속한 대역의 브로드캐스트 주소로 모두 보낸다.
        // 랜카드가 여러 개이거나 대역이 나뉜 사무실에서도 닿게 하기 위해서다.
        foreach (var target in BroadcastTargets())
        {
            try
            {
                await client.SendAsync(question, question.Length, new IPEndPoint(target, Port));
            }
            catch (SocketException)
            {
                // 이 경로로는 보낼 수 없다. 다른 경로를 계속 시도한다.
            }
        }

        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(token);
        deadline.CancelAfter(waitFor);

        try
        {
            while (!deadline.IsCancellationRequested)
            {
                var result = await client.ReceiveAsync(deadline.Token);
                var text = Encoding.UTF8.GetString(result.Buffer);

                if (!text.StartsWith(AnswerPrefix, StringComparison.Ordinal)) continue;

                var payload = text[AnswerPrefix.Length..];
                var server = IpcJson.Deserialize<DiscoveredServer>(payload);

                if (server is null || string.IsNullOrWhiteSpace(server.Url)) continue;

                server.RespondedFrom = result.RemoteEndPoint.Address.ToString();
                found[server.Url] = server;
            }
        }
        catch (OperationCanceledException)
        {
            // 정해진 시간이 다 됐다. 지금까지 모은 것을 돌려준다.
        }
        catch (SocketException)
        {
            // 수신 중 문제가 생겨도 지금까지 모은 것은 쓸 수 있다.
        }

        return found.Values.OrderBy(s => s.MachineName).ToList();
    }

    /// <summary>문의를 보낼 브로드캐스트 주소들.</summary>
    private static IEnumerable<IPAddress> BroadcastTargets()
    {
        yield return IPAddress.Broadcast;

        foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (network.OperationalStatus != OperationalStatus.Up) continue;
            if (network.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;

            foreach (var address in network.GetIPProperties().UnicastAddresses)
            {
                if (address.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                if (address.IPv4Mask is null) continue;

                var broadcast = CalculateBroadcast(address.Address, address.IPv4Mask);
                if (broadcast is not null) yield return broadcast;
            }
        }
    }

    /// <summary>주소와 넷마스크로 그 대역의 브로드캐스트 주소를 구한다.</summary>
    private static IPAddress? CalculateBroadcast(IPAddress address, IPAddress mask)
    {
        var addressBytes = address.GetAddressBytes();
        var maskBytes = mask.GetAddressBytes();

        if (addressBytes.Length != maskBytes.Length) return null;

        var result = new byte[addressBytes.Length];
        for (var i = 0; i < result.Length; i++)
            result[i] = (byte)(addressBytes[i] | (byte)~maskBytes[i]);

        return new IPAddress(result);
    }
}
