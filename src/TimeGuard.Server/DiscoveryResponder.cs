using System.Net;
using System.Net.Sockets;
using System.Text;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;

namespace Hanil.TimeGuard.Server;

/// <summary>
/// 사내망에서 "서버 계십니까" 하고 묻는 신호에 자기 주소를 알려 준다.
///
/// 직원 PC 마다 서버 IP 를 받아 적어 넣지 않아도 되게 하기 위한 것이다.
/// 알려 주는 내용은 접속 주소와 서버 PC 이름뿐이며, 이것만으로는 아무것도 할 수 없다.
/// 등록하려면 등록 키가 따로 필요하다.
/// </summary>
public sealed class DiscoveryResponder : BackgroundService
{
    private readonly IServer _server;
    private readonly IConfiguration _configuration;
    private readonly ILogger<DiscoveryResponder> _logger;

    public DiscoveryResponder(IServer server, IConfiguration configuration, ILogger<DiscoveryResponder> logger)
    {
        _server = server;
        _configuration = configuration;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        UdpClient listener;

        try
        {
            listener = new UdpClient();
            listener.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
            listener.Client.Bind(new IPEndPoint(IPAddress.Any, ServerDiscovery.Port));
        }
        catch (SocketException ex)
        {
            // 검색 기능이 없어도 주소를 직접 적어 등록할 수 있으므로 서버는 계속 동작한다.
            _logger.LogWarning(ex, "사내망 검색 응답 기능을 켜지 못했습니다. 포트 {Port} 를 다른 프로그램이 쓰고 있을 수 있습니다.",
                ServerDiscovery.Port);
            return;
        }

        using (listener)
        {
            _logger.LogInformation("사내망에서 이 서버를 찾을 수 있습니다. (UDP {Port})", ServerDiscovery.Port);

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    var request = await listener.ReceiveAsync(stoppingToken);
                    var text = Encoding.UTF8.GetString(request.Buffer);

                    if (text != ServerDiscovery.Question) continue;

                    var answer = BuildAnswer();
                    if (answer is null) continue;

                    await listener.SendAsync(answer, answer.Length, request.RemoteEndPoint);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    _logger.LogDebug(ex, "검색 문의를 처리하지 못했습니다.");
                }
            }
        }
    }

    /// <summary>지금 이 서버에 접속할 수 있는 주소를 담은 응답을 만든다.</summary>
    private byte[]? BuildAnswer()
    {
        var url = ResolveReachableUrl();
        if (url is null) return null;

        var payload = IpcJson.Serialize(new DiscoveredServer
        {
            Url = url,
            MachineName = Environment.MachineName,
            Version = typeof(DiscoveryResponder).Assembly.GetName().Version?.ToString() ?? "1.0.0"
        });

        return Encoding.UTF8.GetBytes(ServerDiscovery.AnswerPrefix + payload);
    }

    /// <summary>
    /// 다른 PC 가 실제로 접속할 수 있는 주소를 만든다.
    /// 설정에는 0.0.0.0 처럼 "모든 주소" 로 적혀 있으므로 이 PC 의 실제 주소로 바꿔 준다.
    /// </summary>
    private string? ResolveReachableUrl()
    {
        var addresses = _server.Features.Get<IServerAddressesFeature>()?.Addresses;
        var listening = addresses?.FirstOrDefault()
                        ?? _configuration["Kestrel:Endpoints:Https:Url"]
                        ?? _configuration["Kestrel:Endpoints:Http:Url"];

        if (string.IsNullOrWhiteSpace(listening)) return null;
        if (!Uri.TryCreate(listening, UriKind.Absolute, out var uri)) return null;

        var host = uri.Host;

        // 0.0.0.0, [::], * 는 "모든 주소" 라는 뜻이라 그대로는 접속에 쓸 수 없다.
        if (host is "0.0.0.0" or "*" or "+" or "[::]" or "::")
        {
            host = FindLocalAddress();
            if (host is null) return null;
        }

        return $"{uri.Scheme}://{host}:{uri.Port}";
    }

    /// <summary>이 PC 의 사내망 주소를 찾는다.</summary>
    private static string? FindLocalAddress()
    {
        try
        {
            foreach (var network in System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces())
            {
                if (network.OperationalStatus != System.Net.NetworkInformation.OperationalStatus.Up) continue;
                if (network.NetworkInterfaceType == System.Net.NetworkInformation.NetworkInterfaceType.Loopback) continue;

                foreach (var address in network.GetIPProperties().UnicastAddresses)
                {
                    if (address.Address.AddressFamily != AddressFamily.InterNetwork) continue;

                    var text = address.Address.ToString();
                    if (text.StartsWith("169.254.", StringComparison.Ordinal)) continue; // 주소를 못 받은 상태

                    return text;
                }
            }
        }
        catch (Exception)
        {
            // 주소를 찾지 못하면 검색 응답만 못 할 뿐이다.
        }

        return null;
    }
}
