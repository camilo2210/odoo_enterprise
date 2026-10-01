import { expect, test, beforeEach, describe } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { WebClient } from "@web/webclient/webclient";
import { contains, getService, mockService, mountView, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";

import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { checkKpiHeader } from "./timesheet_kpi_leaderboard_header_helpers";
import { defineTimesheetModels } from "./sale_timesheet_models";

defineTimesheetModels();
beforeEach(patchSession);
describe.current.tags("desktop");

test("hr.timesheet (list)(kpi)(leaderboard): Check basics with leaderboard feature on.", async() => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard span:contains('...')").toHaveCount(0);
});

test("hr.timesheet (list)(kpi)(leaderboard): Check basics with leaderboard feature off.", async() => {
    onRpc("get_timesheet_ranking_data", (params) => {
        expect(params.model).toBe("res.company");
        expect.step(params.method);
        return {};
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
    });
    await checkKpiHeader(false);
});

test("hr.timesheet (list)(kpi)(leaderboard): Check that headers displays current month data", async() => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
    });
    await checkKpiHeader();
    // default date is 2019-03-11, as defined by the framework
    expect("div[name=worked_time_kpi][title*='March']").toHaveCount(1);
    expect("div[name=billable_time_kpi][title*='March']").toHaveCount(1);
    expect("div[name=billing_rate_kpi][title*='March']").toHaveCount(1);
});

test("hr.timesheet (list)(kpi)(leaderboard): Check basics, view is grouped.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
        groupBy: ["project_id"],
    });
    await checkKpiHeader();
});

test("hr.timesheet (list)(kpi)(leaderboard): Check basics, view is grouped multiple times.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
        groupBy: ["project_id", "task_id", "name"],
    });
    await checkKpiHeader();
});

test("hr.timesheet (list)(kpi)(leaderboard): Check that button redirects to timesheet assistant.", async() => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
    });
    mockService("action", {
        doAction: async (actionRequest, options = {}) => {
            expect(actionRequest).toBe("hr_timesheet_activitywatch_action");
            expect.step("hr_timesheet_activitywatch_action");
        }
    });
    await checkKpiHeader();
    await contains("div[name=open_timesheet_assistant] > a").click();
    await animationFrame();
    expect.verifySteps(["hr_timesheet_activitywatch_action"], {
        message: "The open timesheet assistant button should trigger 'hr_timesheet_activitywatch_action'",
    });
});

test("hr.timesheet (list)(kpi)(leaderboard): Check billable time button filters billable timesheets.", async() => {
    await mountView({
        resModel: "account.analytic.line",
        type: "list",
    });
    await checkKpiHeader();
    expect(".o_pager").toHaveCount(1);
    expect(".o_pager").toHaveText("1-6 / 6");
    expect(".o_searchview_facet").toHaveCount(0);
    expect(".o_data_row").toHaveCount(6);
    await contains(".o_show_billable_timesheets_button").click();
    await animationFrame();
    expect(".o_pager").toHaveCount(1);
    expect(".o_pager").toHaveText("1-3 / 3");
    expect(".o_searchview_facet").toHaveCount(1);
    expect(".o_data_row").toHaveCount(3);
});

test("hr.timesheet (list)(kpi)(leaderboard): switch view with GroupBy.", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "grid"],
            [false, "list"],
        ],
        context: { group_by: ["project_id", "task_id"] },
    });
    await contains(".o_switch_view.o_list").click();
    await animationFrame();
    await checkKpiHeader();
});
