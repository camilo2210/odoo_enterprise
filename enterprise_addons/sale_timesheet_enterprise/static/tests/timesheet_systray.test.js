import { WebClient } from "@web/webclient/webclient";
import { test, beforeEach, expect } from "@odoo/hoot";
import { contains, getService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { defineTimesheetModels } from "./sale_timesheet_models";
import { setupTimesheetEnvironment } from "@timesheet_grid/../tests/timesheet_timer_helpers";

defineTimesheetModels();
const env = setupTimesheetEnvironment();
let pyEnv;

beforeEach(() => {
    ({ pyEnv } = env);
});

test.tags("desktop");
test("Basic systray actions", async () => {
    await mountWithCleanup(WebClient);
    const saleLineId = pyEnv["sale.order.line"].create({ name: "Sale Order Line 1" });
    const [projectId] = pyEnv["project.project"].create([
        {
            allow_billable: true,
            allow_timesheets: true,
            name: "project_test",
        },
    ]);
    pyEnv["project.task"].create([
        {
            name: "Task 1",
            project_id: projectId,
            sale_line_id: saleLineId,
        },
    ]);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains("div[name='project_id'] input.o_input").edit("project_test");
    await contains("div[name='task_id'] input.o_input").edit("Task 1");
    await contains("input[type='checkbox']").click();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    expect("input[type='checkbox']:checked").toHaveCount(1, {
        message: "The Is_billable in the systray should remember it has been checked",
    });
    await contains("input[type='checkbox']").click();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    expect("input[type='checkbox']:checked").toHaveCount(0, {
        message: "The Is_billable in systray should remember it has been unchecked",
    });
});

test("Existing timesheets retain their database is_billable value", async () => {
    const saleLineId = pyEnv["sale.order.line"].create({ name: "Sale Order Line 1" });
    const [projectId] = pyEnv["project.project"].create([
        {
            allow_billable: true,
            allow_timesheets: true,
            name: "project_test",
        },
    ]);
    const [taskId] = pyEnv["project.task"].create([
        {
            name: "Task 1",
            project_id: projectId,
            sale_line_id: saleLineId,
        },
    ]);

    pyEnv["account.analytic.line"].create([
        {
            name: "Database Saved Timesheet",
            project_id: projectId,
            task_id: taskId,
            is_billable: true,
            has_available_so: true,
            unit_amount: 1.5,
            date: luxon.DateTime.now().toISODate(),
        },
    ]);

    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains("*", { text: "Database Saved Timesheet" }).click();
    expect("input[type='checkbox']:checked").toHaveCount(1, {
        message:
            "The is_billable checkbox must remain true when loading an existing timesheet from the database.",
    });
});

test.tags("desktop");
test("A non-billable task is stored as the last visited one", async () => {
    const [projectId] = pyEnv["project.project"].create([
        {
            allow_billable: false,
            allow_timesheets: true,
            name: "project_test",
        },
    ]);
    const [taskId] = pyEnv["project.task"].create([
        {
            name: "Task 1",
            project_id: projectId,
            allow_billable: false,
            allow_timesheets: true,
        },
    ]);

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        res_id: taskId,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    });
    await contains("div[name='name'] input").edit("Task 1 renamed");

    expect(JSON.parse(localStorage.getItem("timesheet.preFilledForm") || "{}")).toEqual(
        { task_id: taskId },
        {
            message: "Billability should not decide whether the timer systray offers the task",
        }
    );
});
