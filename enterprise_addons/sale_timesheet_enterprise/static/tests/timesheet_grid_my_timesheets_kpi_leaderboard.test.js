import { expect, test, beforeEach, describe } from "@odoo/hoot";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import { queryAll, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { WebClient } from "@web/webclient/webclient";
import {
    contains,
    getService,
    mockService,
    mountView,
    mountWithCleanup,
    onRpc,
    toggleMenuItem,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";

import { hrTimesheetModels, patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { checkKpiHeader } from "./timesheet_kpi_leaderboard_header_helpers";
import { defineTimesheetModels } from "./sale_timesheet_models";

defineTimesheetModels();
beforeEach(async () => {
    patchSession();
    mockDate("2017-04-25 00:00:00", +1);
    const { HRTimesheet } = hrTimesheetModels;
    HRTimesheet._views.grid = HRTimesheet._views.grid
        .replace('js_class="timesheet_grid"', 'js_class="timesheet_grid_my_timesheets"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
    HRTimesheet._views["grid,1"] = HRTimesheet._views["grid,1"]
        .replace('js_class="timesheet_grid"', 'js_class="timesheet_grid_my_timesheets"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
});
describe.current.tags("desktop");

test("hr.timesheet (grid)(kpi)(leaderboard): Check basics with leaderboard feature on.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard span:contains('...')").toHaveCount(0);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check basics with leaderboard feature off.", async () => {
    onRpc("get_timesheet_ranking_data", (params) => {
        expect(params.model).toBe("res.company");
        expect.step(params.method);
        return {};
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader(false);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that headers displays current month data", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    // here, default date is the mocked date because header props date field is passed
    expect("div[name=worked_time_kpi][title*='April']").toHaveCount(1);
    expect("div[name=billable_time_kpi][title*='April']").toHaveCount(1);
    expect("div[name=billing_rate_kpi][title*='April']").toHaveCount(1);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check basics, view is grouped.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
        groupBy: ["project_id"],
    });
    await checkKpiHeader();
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check basics, view is grouped multiple times.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
        groupBy: ["project_id", "task_id", "name"],
    });
    await checkKpiHeader();
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check kpis with groupBy.", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
    });
    await checkKpiHeader();
    await toggleSearchBarMenu();
    await toggleMenuItem("Task");
    await toggleMenuItem("Project");
    expect("div[name=timesheet_kpi_leaderboard_header]").toBeVisible({
        message:
            "The KPI header should be rendered even if the project_id and task_id are not in the rowFields",
    });
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that button to open timesheet assistant is only shown if the setting is active.", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "timesheet_grid.group_timesheet_assistant") {
            return false;
        }
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    expect("div[name=open_timesheet_assistant]").toHaveCount(0);
    expect.verifySteps(["get_kpi_data", "get_timesheet_ranking_data"]);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that button redirects to timesheet assistant.", async () => {
    mockService("action", {
        doAction: async (actionRequest, options = {}) => {
            expect(actionRequest).toBe("hr_timesheet_activitywatch_action");
            expect.step("hr_timesheet_activitywatch_action");
        },
    });
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains("div[name=open_timesheet_assistant] > a").click();
    await animationFrame();
    expect.verifySteps(["hr_timesheet_activitywatch_action"], {
        message:
            "The open timesheet assistant button should trigger 'hr_timesheet_activitywatch_action'",
    });
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check billable time button filters billable timesheets.", async () => {
    mockDate("2017-01-27 00:00:00", +1);
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_searchview_facet").toHaveCount(0);
    expect(".o_grid_row_title").toHaveCount(6);
    await contains(".o_show_billable_timesheets_button").click();
    await animationFrame();
    expect(".o_searchview_facet").toHaveCount(1);
    expect(".o_grid_row_title").toHaveCount(3);
});

test("hr.timesheet (grid)(kpi)(leaderboard): switch view with GroupBy.", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [
            [false, "list"],
            [false, "grid"],
        ],
        context: { group_by: ["project_id", "task_id"] },
    });
    await checkKpiHeader();
    await contains(".o_switch_view.o_grid").click();
    await animationFrame();
    await checkKpiHeader();
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that confetties are displayed if current employee is first in the leaderboard.", async () => {
    mockDate("2017-02-14 00:00:00", +1);
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(1);
    await contains(".o_view_scale_selector > button").click();
    await contains(".o_scale_button_month").click();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(1);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that confetties are not displayed if current employee is not first in the leaderboard.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(0);
    await contains(".o_view_scale_selector > button").click();
    await contains(".o_scale_button_month").click();
    await contains("span[aria-label='Previous']").click();
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard_confetti").toHaveCount(0);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that the total time is displayed without styling if the total valid time >= total time target.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard span:nth-of-type(5).text-danger").toHaveCount(0);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that '···' is displayed when current employee's ranking > 3.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard span:contains('···')").toHaveCount(1);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that employees are sorted accordingly to the ranking criteria.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    await contains(".modal-content .dropdown-toggle").click();
    await contains(".modal-content .dropdown-menu :eq(1)").click();
    await animationFrame();
    expect(localStorage.getItem("leaderboardType")).toEqual("total_time");
    expect(queryAllTexts(".modal-content .o_employee_name")).toEqual([
        "Administrator",
        "User 4",
        "User 3",
        "User 2",
        "User 1",
    ]);
    await contains(".modal-content .dropdown-toggle").click();
    await contains(".modal-content .dropdown-menu :eq(0)").click();
    await animationFrame();
    expect(localStorage.getItem("leaderboardType")).toEqual("billing_rate");
    expect(queryAllTexts(".modal-content .o_employee_name")).toEqual([
        "User 1",
        "User 2",
        "User 3",
        "User 4",
        "Administrator",
    ]);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that employee's name is displayed in bold if rank > 3.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    expect(queryAll(".o_employee_name").pop().parentNode).toHaveClass("fw-bolder");
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that the month changing buttons work in the leaderboard.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await contains(queryOne(".modal-content [data-icon='chevron_backward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect("span:contains('User 5')").toHaveCount(1);
    expect("span:contains('March 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content [data-icon='chevron_forward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect("span:contains('User 1')").toHaveCount(1);
    expect("span:contains('April 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content [data-icon='chevron_forward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect("span:contains('User 6')").toHaveCount(1);
    expect("span:contains('May 2017')").toHaveCount(1);
    await contains(queryOne(".modal-content [data-icon='chevron_backward']").parentNode.nextSibling).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect("span:contains('User 1')").toHaveCount(1);
    expect("span:contains('April 2017')").toHaveCount(1);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that the 'Show more' and 'Show less' buttons works.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await contains(queryOne(".modal-content .modal-body [data-icon='chevron_backward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    await contains(queryOne(".modal-content .modal-body [data-icon='chevron_backward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    await contains(queryOne(".modal-content .modal-body [data-icon='chevron_backward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect(".modal-body td:contains('Test 10')").toHaveCount(0);
    await contains(".o_leaderboard_modal_table ~ span").click();
    expect(".modal-body td:contains('Test 10')").toHaveCount(1);
    await contains(".o_leaderboard_modal_table ~ span").click();
    expect(".modal-body td:contains('Test 10')").toHaveCount(0);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that tip is visible when leaderboard dialog is opened.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    await contains(".o_timesheet_leaderboard div[role='button']").click();
    await animationFrame();
    expect(".modal-content").toHaveCount(1);
    expect(".modal-content:contains('April 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
    expect(queryAllTexts(".modal-content .o_timesheet_leaderboard_tip span")).toEqual([
        "TIP OF THE DAY",
        "Great work this month!",
    ]);
    await contains(queryOne(".modal-content [data-icon='chevron_backward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect(".modal-content:contains('March 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
    expect(queryAllTexts(".modal-content .o_timesheet_leaderboard_tip span")).toEqual([
        "TIP OF THE DAY",
        "March productivity tip!",
    ]);
    await contains(queryOne(".modal-content [data-icon='chevron_forward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    await contains(queryOne(".modal-content [data-icon='chevron_forward']").parentNode).click();
    expect.verifySteps(["get_timesheet_ranking_data"]);
    expect(".modal-content:contains('May 2017')").toHaveCount(1);
    expect(".modal-content .o_timesheet_leaderboard_tip").toHaveCount(1);
    expect(queryAllTexts(".modal-content .o_timesheet_leaderboard_tip span")).toEqual([
        "TIP OF THE DAY",
        "May excellence tip!",
    ]);
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that the indicators are replaced by text if current employee's billing rate <= 0.", async () => {
    mockDate("2017-03-09 00:00:00", +1);
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    await checkKpiHeader();
    expect(".o_timesheet_leaderboard span").toHaveText("Record timesheets to earn your rank!");
});

test("hr.timesheet (grid)(kpi)(leaderboard): Check that navigation updates the KPIs.", async () => {
    await mountView({
        resModel: "account.analytic.line",
        type: "grid",
    });
    expect.verifySteps(["get_kpi_data", "get_timesheet_ranking_data"]);

    expect(queryAllTexts("div[name=period] span")).toEqual(["APR", "2017"]);
    expect("div[name=worked_time_kpi] > span").toHaveText("60");
    expect("div[name=worked_time_kpi][title*='April']").toHaveCount(1);
    expect("div[name=billable_time_kpi] > span > span:eq(0)").toHaveText("30");
    expect("div[name=billable_time_kpi] > span > span.small").toHaveText("/ 60");
    expect("div[name=billable_time_kpi][title*='April']").toHaveCount(1);
    expect("div[name=billing_rate_kpi] > span").toHaveText("50%");
    expect("div[name=billing_rate_kpi][title*='April']").toHaveCount(1);
    expect("div[name=billing_rate_kpi] > span").toHaveClass("text-danger");

    await contains(".o_grid_navigation_buttons > div > button > span[data-icon='east']").click();
    await contains(".o_grid_navigation_buttons > div > button > span[data-icon='east']").click();
    expect.verifySteps(["get_kpi_data", "get_timesheet_ranking_data"]);
    expect(queryAllTexts("div[name=period] span")).toEqual(["MAY", "2017"]);
    expect("div[name=worked_time_kpi] > span").toHaveText("20");
    expect("div[name=worked_time_kpi][title*='May']").toHaveCount(1);
    expect("div[name=billable_time_kpi] > span > span:eq(0)").toHaveText("20");
    expect("div[name=billable_time_kpi] > span > span.small").toHaveText("/ 20");
    expect("div[name=billable_time_kpi][title*='May']").toHaveCount(1);
    expect("div[name=billing_rate_kpi] > span").toHaveText("100%");
    expect("div[name=billing_rate_kpi][title*='May']").toHaveCount(1);
    expect("div[name=billing_rate_kpi] > span").toHaveClass("text-success");

    await contains(".o_view_scale_selector .scale_button_selection").click();
    await contains(".o-dropdown--menu .o_scale_button_month").click();
    expect(queryAllTexts("div[name=period] span")).toEqual(["MAY", "2017"]);
    expect("div[name=worked_time_kpi] > span").toHaveText("20");
    expect("div[name=billable_time_kpi] > span > span:eq(0)").toHaveText("20");
    expect("div[name=billable_time_kpi] > span > span.small").toHaveText("/ 20");
    expect("div[name=billing_rate_kpi] > span").toHaveText("100%");
    expect("div[name=billing_rate_kpi] > span").toHaveClass("text-success");

    await contains(".o_grid_navigation_buttons > button:text('Today')").click();
    await animationFrame();
    expect.verifySteps(["get_kpi_data", "get_timesheet_ranking_data"]);
    expect(queryAllTexts("div[name=period] span")).toEqual(["APR", "2017"]);
    expect("div[name=worked_time_kpi] > span").toHaveText("60");
    expect("div[name=billable_time_kpi] > span > span:eq(0)").toHaveText("30");
    expect("div[name=billable_time_kpi] > span > span.small").toHaveText("/ 60");
    expect("div[name=billing_rate_kpi] > span").toHaveText("50%");
    expect("div[name=billing_rate_kpi] > span").toHaveClass("text-danger");
});
