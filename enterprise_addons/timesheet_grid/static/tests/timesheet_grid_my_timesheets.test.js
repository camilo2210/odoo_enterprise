import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { advanceTime, animationFrame, click, hover, queryAll, queryFirst } from "@odoo/hoot-dom";
import {
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
    removeFacet,
} from "@web/../tests/web_test_helpers";
import { Domain } from "@web/core/domain";
import { WebClient } from "@web/webclient/webclient";

import { patchSession } from "@hr_timesheet/../tests/hr_timesheet_models";
import { defineTimesheetModels, HRTimesheet } from "./hr_timesheet_models";

defineTimesheetModels();

beforeEach(() => {
    patchSession();
    HRTimesheet._views.grid = HRTimesheet._views.grid
        .replace('js_class="timesheet_grid"', 'js_class="timesheet_grid_my_timesheets"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
    HRTimesheet._views["grid,1"] = HRTimesheet._views["grid,1"]
        .replace('js_class="timesheet_grid"', 'js_class="timesheet_grid_my_timesheets"')
        .replace('widget="float_time"', 'widget="timesheet_uom"');
});
onRpc("get_last_validated_timesheet_date", () => "2017-01-25");

test("hr.timesheet (grid): sample data", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        arch: HRTimesheet._views.grid.replace(
            'js_class="timesheet_grid_my_timesheets"',
            'js_class="timesheet_grid_my_timesheets" sample="1"'
        ),
        groupBy: ["employee_id", "task_id"],
        domain: Domain.FALSE.toList(),
    });

    expect(".o_grid_view").toHaveCount(1, {
        message: "The view should be correctly rendered with the sample data enabled when no data is found",
    });
    expect(".o_grid_add_line a").toHaveCount(0, {
        message: "The 'Add a line' button should not be visible inside the row added via the sample data",
    });
    expect(".o_grid_button_add:visible").toHaveCount(1, {
        message: "The 'Add a line' button should be visible",
    });
});

test("hr.timesheet (grid): 'Add a line' should be displayed when display_empty=true", async () => {
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        arch: HRTimesheet._views.grid.replace(
            'js_class="timesheet_grid_my_timesheets"',
            'js_class="timesheet_grid_my_timesheets" display_empty="1"'
        ),
    });

    expect(".o_grid_add_line a").toHaveCount(1, {
        message: "The Add a line button should be displayed even if there is no data",
    });
    expect(".o_grid_button_add:visible").toHaveCount(1, {
        message: "The 'Add a line' button in the control panel should be visible",
    });
    expect(".o_grid_renderer .o_grid_add_line a").toHaveText("Add a line", {
        message: "A button `Add a line` should be displayed in the grid view",
    });

    await click(".o_grid_add_line a");
    await animationFrame();
    expect(".modal").toHaveCount(1, {
        message: "A model should be displayed",
    });

    await click(".modal .modal-footer button.o_form_button_cancel");
    await animationFrame();
    expect(".o_grid_add_line a").toHaveCount(1, {
        message: "No Add a line button should be displayed when no data is found",
    });
    expect(".o_grid_button_add:visible").toHaveCount(1, {
        message: "'Add a line' control panel button should be visible",
    });
});

test("hr.timesheet (grid): basics without Add a line button", async () => {
    onRpc("get_last_validated_timesheet_date", () => "2017-01-30");
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["project_id", "task_id"],
    });

    expect(".o_grid_add_line .btn-link").toHaveCount(0, {
        message: "'Add a line' button should be displayed",
    });
});

test("hr.timesheet (grid): display sample data and then data + fetch last validate timesheet date", async () => {
    HRTimesheet._views.grid = HRTimesheet._views.grid.replace("<grid", "<grid sample='1'");
    onRpc("get_daily_working_hours", () => ({
        "2017-01-24": 4,
        "2017-01-25": 4,
    }));
    onRpc("get_last_validated_timesheet_date", ({ method }) => expect.step(method));

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "account.analytic.line",
        type: "ir.actions.act_window",
        views: [[false, "grid"]],
        context: { search_default_nothing: 1 },
    });

    expect(".o_view_sample_data").toHaveCount(1);
    await removeFacet("Nothing");
    expect(".o_grid_sample_data").toHaveCount(0);
    expect(".o_grid_row_title").toHaveCount(6);
    expect.verifySteps(["get_last_validated_timesheet_date"]); // the rpc should be called only once
});

describe.current.tags("desktop");
test("hr.timesheet (grid): check that individual and total overtime are properly displayed", async () => {
    onRpc("get_daily_working_hours", () => ({
        "2017-01-22": 0,
        "2017-01-23": 7,
        "2017-01-24": 7,
        "2017-01-25": 7,
        "2017-01-26": 7,
        "2017-01-27": 7,
        "2017-01-28": 0,
    }));
    await mountView({
        type: "grid",
        resModel: "account.analytic.line",
        groupBy: ["project_id", "task_id"],
    });

    const columnTotalEls = queryAll(".o_grid_column_total");
    let dangerColumnTotalCells = 0;
    let warningColumnTotalCells = 0;
    let emptyColumnTotalCells = 0;
    let columnTotalEl;

    for (const node of columnTotalEls) {
        if (!columnTotalEl && queryFirst(".o_grid_bar_chart_total_title", { root: node })) {
            columnTotalEl = node;
        }
        if (node.classList.contains("o_grid_bar_chart_container")) {
            continue;
        }
        const columnTotalTitleEl = queryFirst(".o_grid_bar_chart_total_title", { root: node });
        if (!columnTotalTitleEl) {
            emptyColumnTotalCells++;
        } else if (queryFirst("span.text-danger", { root: columnTotalTitleEl })) {
            dangerColumnTotalCells++;
        } else if (queryFirst("span.text-success", { root: columnTotalTitleEl })) {
            warningColumnTotalCells++;
        }
    }

    expect(emptyColumnTotalCells).toBe(4, {
        message:
            "4 column totals should not have any number since the employee has recorded nothing",
    });
    expect(dangerColumnTotalCells).toBe(3, {
        message:
            "3 column totals should have a total displayed in red since the employee has not done all his working hours",
    });
    expect(warningColumnTotalCells).toBe(1, {
        message:
            "1 column totals should have a total displayed in green since the employee has done extra working hours",
    });
    expect(".o_grid_bar_chart_container .o_grid_bar_chart_overtime").toHaveCount(4, {
        message: "4 overtimes indication should be displayed in 4 cells displaying barchart total",
    });
    expect(
        ".o_grid_bar_chart_container:not(.o_grid_highlighted) .o_grid_bar_chart_overtime"
    ).toHaveCount(4, {
        message:
            "4 overtimes indication should be displayed in 4 cells displaying barchart total should not be visible",
    });

    await hover(columnTotalEl);
    await animationFrame();
    await advanceTime(10); // debounce on mouse over event.
    expect(".o_grid_bar_chart_container.o_grid_highlighted .o_grid_bar_chart_overtime").toBeVisible(
        {
            message: "The overtime of the total column hovered should be visible",
        }
    );

    const overtimeClasses = ["text-danger", "text-success", "text-danger", "text-danger"];
    queryAll(".o_grid_bar_chart_container .o_grid_bar_chart_overtime").forEach((node, i) =>
        expect(node).toHaveClass(overtimeClasses[i], {
            message: "Daily overtime should have been displayed in different color",
        })
    );

    expect(
        ".o_grid_highlightable.position-md-sticky.border-success.bg-success-subtle.text-success"
    ).toHaveCount(1, {
        message:
            "Total overtime should be displayed in green because employees have done more work than the normal hours",
    });
});
