using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Core.Server;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Hanil.TimeGuard.Service;

/// <summary>
/// 이름 있는 파이프로 상태 조회와 설정 변경 요청을 받는다.
/// 상태 조회는 누구나 할 수 있고, 설정 변경은 관리자 비밀번호가 있어야 한다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class ControlServer : BackgroundService
{
    private const int MaxConcurrentClients = 8;

    private readonly ServiceState _state;
    private readonly ILogger<ControlServer> _logger;

    public ControlServer(ServiceState state, ILogger<ControlServer> logger)
    {
        _state = state;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var listeners = Enumerable
            .Range(0, MaxConcurrentClients)
            .Select(_ => Task.Run(() => ListenLoopAsync(stoppingToken), stoppingToken))
            .ToArray();

        await Task.WhenAll(listeners);
    }

    private async Task ListenLoopAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                using var server = CreateServer();
                await server.WaitForConnectionAsync(stoppingToken);
                await ServeAsync(server, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                return;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "제어 연결 처리 중 오류가 발생했습니다.");
                try { await Task.Delay(TimeSpan.FromSeconds(1), stoppingToken); }
                catch (OperationCanceledException) { return; }
            }
        }
    }

    /// <summary>
    /// 인증된 사용자면 연결할 수 있게 접근 권한을 설정한다.
    /// 설정을 실제로 바꾸려면 그 위에 비밀번호 확인을 한 번 더 거쳐야 한다.
    /// </summary>
    private static NamedPipeServerStream CreateServer()
    {
        var security = new PipeSecurity();

        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.AuthenticatedUserSid, null),
            PipeAccessRights.ReadWrite,
            AccessControlType.Allow));

        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
            PipeAccessRights.FullControl,
            AccessControlType.Allow));

        security.AddAccessRule(new PipeAccessRule(
            new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
            PipeAccessRights.FullControl,
            AccessControlType.Allow));

        return NamedPipeServerStreamAcl.Create(
            IpcNames.PipeName,
            PipeDirection.InOut,
            MaxConcurrentClients,
            PipeTransmissionMode.Byte,
            PipeOptions.Asynchronous,
            inBufferSize: 64 * 1024,
            outBufferSize: 64 * 1024,
            pipeSecurity: security);
    }

    private async Task ServeAsync(NamedPipeServerStream server, CancellationToken stoppingToken)
    {
        using var reader = new StreamReader(server, new UTF8Encoding(false), leaveOpen: true);
        using var writer = new StreamWriter(server, new UTF8Encoding(false), leaveOpen: true) { AutoFlush = true };

        // 한 연결에서 여러 요청을 처리한다(에이전트가 1초마다 상태를 물어보는 용도).
        while (!stoppingToken.IsCancellationRequested && server.IsConnected)
        {
            var line = await reader.ReadLineAsync(stoppingToken);
            if (line is null) break;

            IpcResponse response;
            try
            {
                var request = IpcJson.Deserialize<IpcRequest>(line);
                response = request is null
                    ? IpcResponse.Fail("요청을 해석하지 못했습니다.")
                    : Handle(request, server);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "요청 처리 중 오류가 발생했습니다.");
                response = IpcResponse.Fail($"요청 처리 중 오류: {ex.Message}");
            }

            await writer.WriteLineAsync(IpcJson.Serialize(response));
        }
    }

    private IpcResponse Handle(IpcRequest request, NamedPipeServerStream server)
    {
        switch (request.Command?.ToUpperInvariant())
        {
            case IpcCommands.Ping:
                return IpcResponse.Success("PONG");

            case IpcCommands.Status:
                return IpcResponse.Success(IpcJson.Serialize(BuildStatus()));

            case IpcCommands.GetConfig:
                return Authorized(request, server, out var getError, out _)
                    ? IpcResponse.Success(IpcJson.Serialize(Redact(_state.Snapshot())))
                    : IpcResponse.Fail(getError);

            case IpcCommands.SetConfig:
                return HandleSetConfig(request, server);

            case IpcCommands.SetPassword:
                return HandleSetPassword(request, server);

            case IpcCommands.Extend:
                return HandleExtend(request, server);

            case IpcCommands.Suspend:
                return HandleSuspend(request, server);

            case IpcCommands.SetEnabled:
                return HandleSetEnabled(request, server);

            case IpcCommands.GetLog:
                return HandleGetLog(request, server);

            case IpcCommands.CancelShutdown:
                return HandleCancelShutdown(request, server);

            case IpcCommands.RequestExtension:
                return HandleRequestExtension(request, server);

            default:
                return IpcResponse.Fail($"알 수 없는 명령입니다: {request.Command}");
        }
    }

    private IpcResponse HandleSetConfig(IpcRequest request, NamedPipeServerStream server)
    {
        if (ServerManaged(out var managed)) return managed;
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var incoming = IpcJson.Deserialize<GuardConfig>(request.Payload);
        if (incoming is null) return IpcResponse.Fail("설정 내용을 해석하지 못했습니다.");

        if (incoming.Enabled && !_state.PasswordIsSet && string.IsNullOrEmpty(incoming.PasswordHash))
            return IpcResponse.Fail("감시를 켜기 전에 관리자 비밀번호를 먼저 설정해 주세요.");

        _state.Update(config =>
        {
            // 비밀번호는 이 명령으로 바꾸지 않는다. 전용 명령으로만 변경한다.
            var currentHash = config.PasswordHash;

            config.Enabled = incoming.Enabled;
            config.Action = incoming.Action;
            config.Schedule = incoming.Schedule ?? config.Schedule;
            config.Warnings = incoming.Warnings ?? config.Warnings;
            config.Holidays = incoming.Holidays ?? config.Holidays;
            config.HolidayPolicy = incoming.HolidayPolicy;
            config.ExemptUsers = incoming.ExemptUsers ?? config.ExemptUsers;
            config.PasswordHash = currentHash;
        }, user, "설정을 변경했습니다.");

        return IpcResponse.Success();
    }

    private IpcResponse HandleSetPassword(IpcRequest request, NamedPipeServerStream server)
    {
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var payload = IpcJson.Deserialize<SetPasswordRequest>(request.Payload);
        if (payload is null) return IpcResponse.Fail("비밀번호 정보를 해석하지 못했습니다.");

        if (!PasswordHasher.IsAcceptable(payload.NewPassword, out var problem))
            return IpcResponse.Fail(problem);

        var hash = PasswordHasher.Hash(payload.NewPassword);
        _state.Update(config => config.PasswordHash = hash, user, "관리자 비밀번호를 변경했습니다.");

        return IpcResponse.Success();
    }

    private IpcResponse HandleExtend(IpcRequest request, NamedPipeServerStream server)
    {
        if (ServerManaged(out var managed)) return managed;
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var payload = IpcJson.Deserialize<ExtendRequest>(request.Payload);
        if (payload is null) return IpcResponse.Fail("연장 정보를 해석하지 못했습니다.");

        if (payload.Minutes <= 0)
        {
            _state.Update(config => config.ExtensionUntil = null, user, "연장을 취소했습니다.");
            return IpcResponse.Success();
        }

        if (payload.Minutes > 24 * 60)
            return IpcResponse.Fail("연장은 한 번에 최대 1440분(24시간)까지 가능합니다.");

        var until = DateTimeOffset.Now.AddMinutes(payload.Minutes);
        _state.Update(config => config.ExtensionUntil = until, user,
            $"{payload.Minutes}분 연장했습니다({until:yyyy-MM-dd HH:mm} 까지).");

        return IpcResponse.Success(IpcJson.Serialize(until));
    }

    private IpcResponse HandleSuspend(IpcRequest request, NamedPipeServerStream server)
    {
        if (ServerManaged(out var managed)) return managed;
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var payload = IpcJson.Deserialize<SuspendRequest>(request.Payload);
        if (payload is null) return IpcResponse.Fail("일시 중지 정보를 해석하지 못했습니다.");

        if (payload.Minutes <= 0)
        {
            _state.Update(config => config.SuspendedUntil = null, user, "일시 중지를 해제했습니다.");
            return IpcResponse.Success();
        }

        var until = DateTimeOffset.Now.AddMinutes(payload.Minutes);
        _state.Update(config => config.SuspendedUntil = until, user,
            $"{payload.Minutes}분 동안 일시 중지했습니다({until:yyyy-MM-dd HH:mm} 까지).");

        return IpcResponse.Success(IpcJson.Serialize(until));
    }

    private IpcResponse HandleSetEnabled(IpcRequest request, NamedPipeServerStream server)
    {
        if (ServerManaged(out var managed)) return managed;
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var payload = IpcJson.Deserialize<SetEnabledRequest>(request.Payload);
        if (payload is null) return IpcResponse.Fail("요청을 해석하지 못했습니다.");

        if (payload.Enabled && !_state.PasswordIsSet)
            return IpcResponse.Fail("감시를 켜기 전에 관리자 비밀번호를 먼저 설정해 주세요.");

        _state.Update(config => config.Enabled = payload.Enabled, user,
            payload.Enabled ? "감시를 켰습니다." : "감시를 껐습니다.");

        return IpcResponse.Success();
    }

    private IpcResponse HandleGetLog(IpcRequest request, NamedPipeServerStream server)
    {
        if (!Authorized(request, server, out var error, out _)) return IpcResponse.Fail(error);

        var payload = IpcJson.Deserialize<GetLogRequest>(request.Payload) ?? new GetLogRequest();
        return IpcResponse.Success(IpcJson.Serialize(_state.Log.Tail(payload.Lines)));
    }

    private IpcResponse HandleCancelShutdown(IpcRequest request, NamedPipeServerStream server)
    {
        if (!Authorized(request, server, out var error, out var user)) return IpcResponse.Fail(error);

        var ok = Interop.PowerController.AbortShutdown();
        _state.Log.Write("조치", ok
            ? $"예약된 종료를 취소했습니다. (요청자: {user})"
            : $"종료 취소를 시도했지만 취소할 수 있는 종료가 없었습니다. (요청자: {user})");

        return ok
            ? IpcResponse.Success()
            : IpcResponse.Fail("취소할 수 있는 종료가 없습니다. 이미 종료가 시작되었을 수 있습니다.");
    }

    /// <summary>
    /// 사용자가 올리는 연장 요청. 관리자 비밀번호가 필요 없다.
    /// 서비스가 서버로 전달하고, 승인 여부는 관리자가 웹 화면에서 정한다.
    /// </summary>
    private IpcResponse HandleRequestExtension(IpcRequest request, NamedPipeServerStream server)
    {
        if (!_state.ServerMode)
            return IpcResponse.Fail("이 PC 는 관리 서버를 쓰지 않습니다. 관리자에게 직접 문의해 주세요.");

        var payload = IpcJson.Deserialize<UserExtensionRequest>(request.Payload);
        if (payload is null) return IpcResponse.Fail("요청 내용을 해석하지 못했습니다.");

        if (payload.Minutes <= 0 || payload.Minutes > 720)
            return IpcResponse.Fail("연장 요청은 1분에서 720분(12시간) 사이로 해 주세요.");

        var user = DescribeCaller(server);
        var settings = ServerSettings.Load();

        if (!settings.IsEnrolled)
            return IpcResponse.Fail("이 PC 가 아직 관리 서버에 등록되지 않았습니다.");

        try
        {
            using var connection = new ServerConnection(settings);

            // 사용자가 창 앞에서 기다리므로 짧게 기다렸다 결과를 돌려준다.
            var (ok, message) = connection
                .RequestExtensionAsync(payload.Minutes, payload.Reason, user)
                .GetAwaiter().GetResult();

            _state.Log.Write("요청", ok
                ? $"{user} 님이 {payload.Minutes}분 연장을 요청했습니다. 사유: {payload.Reason}"
                : $"연장 요청을 보내지 못했습니다: {message}");

            return ok ? IpcResponse.Success(message) : IpcResponse.Fail(message);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "연장 요청을 보내지 못했습니다.");
            return IpcResponse.Fail($"요청을 보내지 못했습니다: {ex.Message}");
        }
    }

    /// <summary>서버가 관리하는 PC 에서는 로컬에서 설정을 바꾸지 못하게 막는다.</summary>
    private bool ServerManaged(out IpcResponse response)
    {
        if (!_state.ServerMode)
        {
            response = IpcResponse.Success();
            return false;
        }

        var url = _state.ServerUrl ?? "관리 서버";
        response = IpcResponse.Fail(
            $"이 PC 는 관리 서버({url})가 설정을 관리합니다. 변경은 서버의 웹 화면에서 해 주세요.");

        return true;
    }

    /// <summary>상태에 서버 관련 정보와 알릴 내용을 덧붙인다.</summary>
    private StatusSnapshot BuildStatus()
    {
        var status = _state.Status;

        status.ServerMode = _state.ServerMode;
        status.ServerReachable = _state.ServerReachable;
        status.ServerUrl = _state.ServerUrl;
        status.Decision = _state.DequeueDecision();

        return status;
    }

    /// <summary>비밀번호를 확인하고, 감사 로그에 남길 호출자 이름을 얻는다.</summary>
    private bool Authorized(IpcRequest request, NamedPipeServerStream server, out string error, out string user)
    {
        user = DescribeCaller(server);
        return _state.Authenticate(request.Password, out error);
    }

    private static string DescribeCaller(NamedPipeServerStream server)
    {
        try
        {
            var name = server.GetImpersonationUserName();
            return string.IsNullOrWhiteSpace(name) ? "(알 수 없음)" : name;
        }
        catch
        {
            return "(알 수 없음)";
        }
    }

    /// <summary>설정을 밖으로 내보낼 때 비밀번호 해시는 지운다.</summary>
    private static GuardConfig Redact(GuardConfig config)
    {
        config.PasswordHash = string.IsNullOrEmpty(config.PasswordHash) ? string.Empty : "(설정됨)";
        return config;
    }
}
