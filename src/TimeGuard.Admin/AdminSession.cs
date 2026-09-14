using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Admin;

/// <summary>
/// 서비스와의 연결과 관리자 비밀번호를 한 번만 확인해 두고 재사용한다.
/// </summary>
internal sealed class AdminSession : IDisposable
{
    private readonly ControlClient _client = new();
    private string? _password;

    /// <summary>서비스가 응답하는지 확인한다.</summary>
    internal bool ServiceAvailable(out string error)
    {
        var response = _client.Send(IpcCommands.Ping);
        error = response.Error ?? string.Empty;
        return response.Ok;
    }

    internal StatusSnapshot? GetStatus() => _client.GetStatus();

    /// <summary>비밀번호를 미리 넣어 둔다(명령줄 사용 시).</summary>
    internal void UsePassword(string? password) => _password = password;

    /// <summary>
    /// 비밀번호가 아직 확인되지 않았으면 물어보고, 서비스에 검증을 맡긴다.
    /// 비밀번호가 설정돼 있지 않은 최초 상태라면 그냥 통과한다.
    /// </summary>
    internal bool EnsureAuthenticated()
    {
        if (_password is not null) return true;

        // 비밀번호가 필요한지 가벼운 명령으로 먼저 확인한다.
        var probe = _client.Send(IpcCommands.GetConfig);
        if (probe.Ok)
        {
            _password = string.Empty;
            return true;
        }

        for (var attempt = 0; attempt < 3; attempt++)
        {
            var password = ConsoleUi.PromptPassword("관리자 비밀번호");
            if (string.IsNullOrEmpty(password))
            {
                ConsoleUi.Warn("입력이 취소되었습니다.");
                return false;
            }

            var check = _client.Send(IpcCommands.GetConfig, password);
            if (check.Ok)
            {
                _password = password;
                return true;
            }

            ConsoleUi.Error(check.Error ?? "비밀번호 확인에 실패했습니다.");
        }

        ConsoleUi.Error("비밀번호를 세 번 잘못 입력했습니다.");
        return false;
    }

    internal IpcResponse Send(string command, string? payload = null)
    {
        if (!EnsureAuthenticated())
            return IpcResponse.Fail("관리자 인증이 필요합니다.");

        return _client.Send(command, _password, payload);
    }

    /// <summary>현재 설정을 가져온다. 비밀번호 해시는 서비스가 지운 상태로 온다.</summary>
    internal GuardConfig? GetConfig()
    {
        var response = Send(IpcCommands.GetConfig);
        if (!response.Ok)
        {
            ConsoleUi.Error(response.Error ?? "설정을 가져오지 못했습니다.");
            return null;
        }

        return IpcJson.Deserialize<GuardConfig>(response.Payload);
    }

    /// <summary>설정을 저장한다. 성공 여부를 돌려주고 실패하면 이유를 출력한다.</summary>
    internal bool SaveConfig(GuardConfig config)
    {
        var response = Send(IpcCommands.SetConfig, IpcJson.Serialize(config));

        if (!response.Ok)
        {
            ConsoleUi.Error(response.Error ?? "설정을 저장하지 못했습니다.");
            return false;
        }

        ConsoleUi.Success("설정을 저장했습니다.");
        return true;
    }

    public void Dispose() => _client.Dispose();
}
