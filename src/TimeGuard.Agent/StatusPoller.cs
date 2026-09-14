using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Agent;

/// <summary>
/// 별도 스레드에서 서비스 상태를 주기적으로 가져온다.
/// UI 스레드가 파이프 대기로 멈추지 않도록 분리했다.
/// </summary>
public sealed class StatusPoller : IDisposable
{
    private static readonly TimeSpan PollInterval = TimeSpan.FromSeconds(1);
    private static readonly TimeSpan RetryInterval = TimeSpan.FromSeconds(5);

    private readonly ControlClient _client = new();
    private readonly CancellationTokenSource _cancellation = new();
    private readonly Thread _thread;

    private volatile StatusSnapshot? _latest;
    private volatile bool _serviceReachable;

    public StatusPoller()
    {
        _thread = new Thread(Run)
        {
            IsBackground = true,
            Name = "TimeGuard 상태 확인"
        };
    }

    /// <summary>가장 최근에 받은 상태. 아직 받은 적이 없으면 null.</summary>
    public StatusSnapshot? Latest => _latest;

    /// <summary>서비스와 통신이 되고 있는지 여부.</summary>
    public bool ServiceReachable => _serviceReachable;

    public void Start() => _thread.Start();

    /// <summary>
    /// 연장 요청을 서비스로 보낸다. 서비스가 서버로 전달한다.
    /// 사용자가 창 앞에서 기다리므로 조금 더 오래 기다린다.
    /// </summary>
    public (bool Ok, string Message) RequestExtension(int minutes, string reason)
    {
        var payload = IpcJson.Serialize(new UserExtensionRequest { Minutes = minutes, Reason = reason });

        // 상태 확인용 연결과 섞이지 않도록 이 요청만 쓰는 연결을 따로 연다.
        using var client = new ControlClient();
        var response = client.Send(IpcCommands.RequestExtension, payload: payload, connectTimeoutMs: 5000);

        return response.Ok
            ? (true, response.Payload ?? "연장 요청을 보냈습니다.")
            : (false, response.Error ?? "요청을 처리하지 못했습니다.");
    }

    private void Run()
    {
        var token = _cancellation.Token;

        while (!token.IsCancellationRequested)
        {
            var status = _client.GetStatus(connectTimeoutMs: 1500);

            if (status is not null)
            {
                _latest = status;
                _serviceReachable = true;
            }
            else
            {
                _serviceReachable = false;
            }

            try
            {
                token.WaitHandle.WaitOne(_serviceReachable ? PollInterval : RetryInterval);
            }
            catch (ObjectDisposedException)
            {
                return;
            }
        }
    }

    public void Dispose()
    {
        try
        {
            _cancellation.Cancel();
            _thread.Join(TimeSpan.FromSeconds(2));
        }
        catch
        {
            // 종료 중 오류는 무시한다.
        }

        _client.Dispose();
        _cancellation.Dispose();
    }
}
