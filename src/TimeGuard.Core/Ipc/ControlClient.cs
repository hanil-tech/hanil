using System.IO.Pipes;
using System.Text;

namespace Hanil.TimeGuard.Core.Ipc;

/// <summary>
/// 서비스의 제어 파이프에 연결하는 클라이언트.
/// 연결은 필요할 때 만들고, 끊기면 다음 호출에서 다시 붙는다.
/// </summary>
public sealed class ControlClient : IDisposable
{
    private readonly string _pipeName;
    private readonly object _gate = new();

    private NamedPipeClientStream? _pipe;
    private StreamReader? _reader;
    private StreamWriter? _writer;

    public ControlClient(string? pipeName = null)
    {
        _pipeName = pipeName ?? IpcNames.PipeName;
    }

    public bool IsConnected => _pipe?.IsConnected == true;

    /// <summary>요청을 보내고 응답을 받는다. 연결이 끊겨 있으면 한 번 다시 연결해 본다.</summary>
    public IpcResponse Send(IpcRequest request, int connectTimeoutMs = 2000)
    {
        lock (_gate)
        {
            for (var attempt = 0; attempt < 2; attempt++)
            {
                try
                {
                    EnsureConnected(connectTimeoutMs);

                    _writer!.WriteLine(IpcJson.Serialize(request));
                    var line = _reader!.ReadLine();

                    if (line is null)
                    {
                        Disconnect();
                        continue; // 서버가 연결을 닫았다. 한 번 더 시도한다.
                    }

                    return IpcJson.Deserialize<IpcResponse>(line)
                           ?? IpcResponse.Fail("서비스 응답을 해석하지 못했습니다.");
                }
                catch (TimeoutException)
                {
                    Disconnect();
                    return IpcResponse.Fail("서비스에 연결하지 못했습니다. 서비스가 실행 중인지 확인해 주세요.");
                }
                catch (Exception ex) when (ex is IOException or ObjectDisposedException or InvalidOperationException)
                {
                    Disconnect();
                    if (attempt == 1) return IpcResponse.Fail($"서비스와 통신하지 못했습니다: {ex.Message}");
                }
                catch (UnauthorizedAccessException)
                {
                    Disconnect();
                    return IpcResponse.Fail("서비스 파이프에 접근할 권한이 없습니다.");
                }
            }

            return IpcResponse.Fail("서비스와 통신하지 못했습니다.");
        }
    }

    public IpcResponse Send(string command, string? password = null, string? payload = null, int connectTimeoutMs = 2000)
        => Send(new IpcRequest { Command = command, Password = password, Payload = payload }, connectTimeoutMs);

    /// <summary>현재 상태를 가져온다. 서비스에 닿지 못하면 null.</summary>
    public StatusSnapshot? GetStatus(int connectTimeoutMs = 2000)
    {
        var response = Send(IpcCommands.Status, connectTimeoutMs: connectTimeoutMs);
        return response.Ok ? IpcJson.Deserialize<StatusSnapshot>(response.Payload) : null;
    }

    private void EnsureConnected(int connectTimeoutMs)
    {
        if (_pipe is { IsConnected: true }) return;

        Disconnect();

        var pipe = new NamedPipeClientStream(".", _pipeName, PipeDirection.InOut, PipeOptions.None);
        pipe.Connect(connectTimeoutMs);

        _pipe = pipe;
        _reader = new StreamReader(pipe, new UTF8Encoding(false), leaveOpen: true);
        _writer = new StreamWriter(pipe, new UTF8Encoding(false), leaveOpen: true) { AutoFlush = true };
    }

    private void Disconnect()
    {
        try { _reader?.Dispose(); } catch { /* 정리 중 오류는 무시한다. */ }
        try { _writer?.Dispose(); } catch { /* 정리 중 오류는 무시한다. */ }
        try { _pipe?.Dispose(); } catch { /* 정리 중 오류는 무시한다. */ }

        _reader = null;
        _writer = null;
        _pipe = null;
    }

    public void Dispose()
    {
        lock (_gate) Disconnect();
    }
}
