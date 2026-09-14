using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Hanil.TimeGuard.Server.Pages;

/// <summary>
/// 승인을 기다리는 PC 수를 모든 화면의 메뉴에 표시한다.
/// 한 화면에만 두면 관리자가 놓치기 쉽다.
/// </summary>
public sealed class PendingCountFilter : IAsyncPageFilter
{
    public Task OnPageHandlerSelectionAsync(PageHandlerSelectedContext context) => Task.CompletedTask;

    public async Task OnPageHandlerExecutionAsync(PageHandlerExecutingContext context, PageHandlerExecutionDelegate next)
    {
        if (context.HandlerInstance is PageModel page && page.User.Identity?.IsAuthenticated == true)
        {
            try
            {
                var db = context.HttpContext.RequestServices.GetRequiredService<GuardDbContext>();

                page.ViewData["WaitingCount"] = await db.Devices
                    .CountAsync(d => d.Approval == ApprovalState.Pending, context.HttpContext.RequestAborted);
            }
            catch (Exception)
            {
                // 이 숫자를 못 구해도 화면은 정상 동작해야 한다.
            }
        }

        await next();
    }
}
