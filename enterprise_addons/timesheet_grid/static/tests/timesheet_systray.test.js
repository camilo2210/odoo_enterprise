import { beforeEach, expect, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { advanceTime, animationFrame, tick } from "@odoo/hoot-mock";
import { triggerHotkey } from "@mail/../tests/mail_test_helpers";
import { user } from "@web/core/user";
import {
    contains,
    getService,
    mountWithCleanup,
    onRpc,
    selectFieldDropdownItem,
    serverState,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { defineTimesheetModels } from "./hr_timesheet_models";
import {
    setupTimesheetEnvironment,
    advanceTimer,
    setPreFilledFormTimesheet,
} from "./timesheet_timer_helpers";

const env = setupTimesheetEnvironment();

let pyEnv;
let sessionData;

defineTimesheetModels();

beforeEach(() => {
    ({ pyEnv, sessionData } = env);
});

test("Basic systray actions", async () => {
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Test 1",
            date: "2019-03-11",
            project_id: 1,
            task_id: false,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);
    expect("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").toHaveCount(1, {
        message: "There should be a button to open the systray",
    });
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();

    expect("div[name='ts_checkin_btn'] > button").toHaveCount(1, {
        message: "There should be a checkin button",
    });
    await contains("div[name='ts_checkin_btn'] > button").click();

    expect(".o_timesheet_inline_form").toHaveCount(1, {
        message: "The timesheet form view should be open inside the popover",
    });
    expect(".field-description textarea").toBeFocused({
        message: "The visible description textarea should automatically gain focus",
    });
    expect("div[name='unit_amount_field_container'] input.o_input").toHaveValue("0h 0m 0s", {
        message: "The timer input should be present and initialized to 0",
    });
    expect(".o_att_timesheet_list .list-group-item").toHaveCount(1, {
        message: "There should be exactly one timesheet in the history list",
    });
    expect(".o_att_timesheet_list .list-group-item").toHaveText(/Test 1/, {
        message: "The timesheet should be in the list",
    });
    expect(".o_att_timesheet_list .list-group-item").toHaveText(/1h 00m/, {
        message: "The list should display the 1 hour duration correctly formatted",
    });
});

test.tags("desktop");
test("ALT + Shift + R shortcut opens the dropdown", async () => {
    await mountWithCleanup(WebClient);
    expect("div.o_timesheet_grid_popover").toHaveCount(0, {
        message: "The dropdown should be closed by default",
    });

    await triggerHotkey("alt+shift+r");
    await animationFrame();
    expect("div.o_timesheet_grid_popover").toHaveCount(1, {
        message: "The dropdown should be opened when pressing ALT + Shift + R",
    });
});

test.tags("desktop");
test("Creating a new timesheet places it at the top of the list", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains(".field-description textarea").edit("My Task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await contains("button:contains('Create')").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveCount(1, {
        message: "The new timesheet should be added to the list",
    });
    expect(".o_att_timesheet_list .list-group-item:first-child").toHaveText(/My Task/, {
        message: "The newly created timesheet should appear at the top of the list",
    });

    // Second entry
    await contains(".field-description textarea").edit("My Brand New Task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await contains("button:contains('Create')").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveCount(2, {
        message: "The new timesheet should be added to the list",
    });
    expect(".o_att_timesheet_list .list-group-item:first-child").toHaveText(/My Brand New Task/, {
        message: "The newly created timesheet should appear at the top of the list",
    });
});

test("Edit and delete an existing timesheet", async () => {
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Old Task",
            date: "2019-03-11",
            project_id: 1,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();

    expect(".o_att_timesheet_form_active_sheet").toHaveCount(1, {
        message: "Clicking the timesheet should open an inline form view",
    });

    await contains(".o_att_timesheet_form_active_sheet .field-description textarea").edit(
        "Updated Task",
        {
            instantly: true,
            confirm: "Tab",
        }
    );
    await tick();

    await contains(".o_att_timesheet_form_active_sheet button.btn-primary").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveText(/Updated Task/, {
        message: "The list item should reflect the new description after saving",
    });

    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();

    await contains(".o_att_timesheet_form_active_sheet button.btn-danger").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveCount(0, {
        message: "The deleted timesheet should be removed from the list",
    });
});

test("Timesheet list displays a scrollbar when overflowing", async () => {
    await mountWithCleanup(WebClient);
    const manyTimesheets = Array.from({ length: 15 }).map((_, i) => ({
        user_id: serverState.userId,
        name: `Task ${i}`,
        date: "2019-03-11",
        project_id: 1,
        unit_amount: 1,
        company_id: user.activeCompany.id,
    }));
    pyEnv["account.analytic.line"].create(manyTimesheets);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    const listEl = document.querySelector(".o_att_timesheet_list");

    expect(listEl.scrollHeight).toBeGreaterThan(listEl.clientHeight, {
        message: "The container should have scrollable overflow content",
    });
});

test("Timer ticks, pauses on focus, and resumes on lost focus", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    const inputSelector = "div[name='unit_amount_field_container'] input.o_input";

    expect(inputSelector).toHaveValue("0h 0m 0s", {
        message: "Timer should start at 0",
    });

    await advanceTimer(3000);

    expect(inputSelector).toHaveValue("0h 0m 3s", {
        message: "3 seconds should have elapsed",
    });

    await contains(inputSelector).click();
    await tick();

    await advanceTimer(2000);

    expect(inputSelector).toHaveValue("0h", {
        message:
            "Timer should pause visual updates while the field is focused and hide the seconds",
    });

    await contains("div[name='name'] textarea").click();
    await tick();

    await advanceTimer(1000);

    expect(inputSelector).toHaveValue("0h 0m 3s", {
        message: "Timer should be paused the 2 seconds spent focused",
    });

    await advanceTimer(57000);

    expect(inputSelector).toHaveValue("0h 1m 0s", {
        message: "57 more seconds should have elapsed",
    });
});

test.tags("desktop");
test("Copy existing timesheet and preserve project and task", async () => {
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Old Task",
            date: "2019-03-11",
            project_id: 1,
            task_id: 1,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();

    await contains("div[name='ts_checkin_btn'] > button").click();
    await selectFieldDropdownItem("project_id", "P1");
    await tick();
    await selectFieldDropdownItem("task_id", "BS task");
    await tick();

    await contains(".o_att_timesheet_copy").click();
    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "The project should be filled automatically",
    });
    expect("div[name='task_id'] input").toHaveValue("BS task", {
        message: "The task should be filled automatically",
    });
});

test.tags("desktop");
test("Data and timer persist for new timesheets when systray is closed and reopened", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains("div[name='name'] textarea").edit("Test Persistence", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await advanceTimer(3000);

    const inputSelector = "div[name='unit_amount_field_container'] input.o_input";
    expect(inputSelector).toHaveValue("0h 0m 3s", {
        message: "3 seconds should have elapsed",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect(".o_timesheet_inline_form").toHaveCount(0, {
        message: "The dropdown should be closed",
    });

    await advanceTime(2000);
    await tick();

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect(".field-description textarea").toHaveValue("Test Persistence", {
        message: "The description should be preserved",
    });
    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "The project should be preserved",
    });

    await advanceTimer(1000);

    expect(inputSelector).toHaveValue("0h 0m 6s", {
        message: "The timer should continue to tick; 3 more seconds have elapsed",
    });
});

test.tags("desktop");
test("Data persists for existing timesheets when systray is closed and reopened", async () => {
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Original Task",
            date: "2019-03-11",
            project_id: 1,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();

    await contains(".o_att_timesheet_form_active_sheet .field-description textarea").edit(
        "Test Persistence Existing",
        {
            instantly: true,
            confirm: "Tab",
        }
    );
    await tick();

    await selectFieldDropdownItem("project_id", "Webocalypse Now");
    await tick();

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect(".o_timesheet_inline_form").toHaveCount(0, {
        message: "The dropdown should be closed",
    });

    await advanceTime(2000);
    await tick();

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect(".o_att_timesheet_form_active_sheet").toHaveCount(1, {
        message: "The form should still be in edit mode for the existing timesheet after reopening",
    });
    expect(".o_att_timesheet_form_active_sheet .field-description textarea").toHaveValue(
        "Test Persistence Existing",
        {
            message: "The description should be preserved",
        }
    );
    expect(".o_att_timesheet_form_active_sheet div[name='project_id'] input").toHaveValue(
        "Webocalypse Now",
        {
            message: "The project should be preserved",
        }
    );
});

test("Edit, verify text wrapping/truncation, and delete an existing timesheet", async () => {
    await mountWithCleanup(WebClient);
    const longText = "Old Task " + "with a very long description ".repeat(5);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: longText,
            date: "2019-03-11",
            project_id: 1,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    const descriptionEl = document.querySelector(
        ".o_att_timesheet_list .list-group-item p.fw-medium"
    );
    expect(descriptionEl).toHaveClass("text-truncate", {
        message: "Long descriptions should have the text-truncate class applied in the list",
    });
    expect(descriptionEl.scrollWidth).toBeGreaterThan(descriptionEl.clientWidth, {
        message:
            "The layout must constrain the paragraph width so the text visually truncates with an ellipsis",
    });

    expect("div[name='total_hours']").toHaveText(/Total\s*1h 00m\s*over\s*8h 00m/, {
        message: "Total hours should be 1 hour",
    });

    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();

    const textarea = document.querySelector(".field-description textarea");
    expect(textarea.style.height).not.toBe("24px", {
        message: "Textarea should dynamically expand its height to fit the long description",
    });

    await contains(".o_att_timesheet_form_active_sheet .field-description textarea").edit(
        "Updated Task",
        {
            instantly: true,
            confirm: "Tab",
        }
    );
    await tick();

    await contains("div[name='unit_amount_field_container'] input").edit("02:00", {
        confirm: "Tab",
    });
    await tick();

    await contains(".o_att_timesheet_form_active_sheet button.btn-primary").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveText(/Updated Task/);

    expect("div[name='total_hours']").toHaveText(/Total\s*2h 00m\s*over\s*8h 00m/, {
        message: "Total hours should update to 2h after saving the modification",
    });

    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();

    await contains(".o_att_timesheet_form_active_sheet button.btn-danger").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item").toHaveCount(0);

    expect("div[name='total_hours']").toHaveText(/Total\s*0h 00m\s*over\s*8h 00m/, {
        message: "Total hours should be back to 0h after deleting the only timesheet",
    });
});

test("Resetting a new timesheet clears the form and drops the timer to 0", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains(".field-description textarea").edit("Task I want to cancel", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await advanceTimer(3000);
    expect("div[name='unit_amount_field_container'] input.o_input").toHaveValue("0h 0m 3s");

    await contains("button:contains('Reset')").click();
    await tick();

    expect(".field-description textarea").toHaveValue("", {
        message: "The description should be completely emptied",
    });

    expect("div[name='unit_amount_field_container'] input.o_input").toHaveValue("0h 0m 0s", {
        message: "The timer should be reset to 0s",
    });
});

test.tags("desktop");
test("Systray gracefully handles a draft with a deleted project without crashing", async () => {
    await mountWithCleanup(WebClient);
    const [projectId] = pyEnv["project.project"].create([
        {
            name: "Doomed Project",
            allow_timesheets: true,
        },
    ]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains("div[name='project_id'] input").edit("Doomed");
    await advanceTime(250);
    await tick();

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    pyEnv["project.project"].unlink([projectId]);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect(".o_timesheet_inline_form").toHaveCount(1, {
        message: "The systray should open without tracebacks",
    });

    expect("div[name='project_id'] input").toHaveValue("Doomed Project", {
        message:
            "The input should display the tuple's cached display_name despite the record being deleted",
    });
});

test.tags("desktop");
test("Info added after a reset/save are correctly saved when closing systray", async () => {
    await mountWithCleanup(WebClient);
    const systrayButton = contains(
        "div.o_menu_systray button.o-dropdown i[data-icon='play_circle']"
    );
    await systrayButton.click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    await contains("button:contains('Reset')").click();
    await tick();

    await contains(".field-description textarea").edit("Task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await systrayButton.click(); // Close
    await systrayButton.click(); // Re-open

    expect("div[name='project_id'] input").toHaveValue("P1");
    expect(".field-description textarea").toHaveValue("Task");

    await contains("button:contains('Create')").click();
    await tick();

    await contains(".field-description textarea").edit("Task #2", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "Webocalypse Now");
    await tick();

    await systrayButton.click(); // Close
    await systrayButton.click(); // Re-open

    expect("div[name='project_id'] input").toHaveValue("Webocalypse Now");
    expect(".field-description textarea").toHaveValue("Task #2");
});

test.tags("desktop");
test("Timer applies configured minimum", async () => {
    sessionData.timesheet_rounding_values = { minimum: 12, rounding: 12 };
    await mountWithCleanup(WebClient);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains(".field-description textarea").edit("Short task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await advanceTimer(10000);
    await contains("button:contains('Create')").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item:first-child").toHaveText(/12m/);
});

test.tags("desktop");
test("Timer applies configured rounding", async () => {
    sessionData.timesheet_rounding_values = { minimum: 12, rounding: 12 };
    await mountWithCleanup(WebClient);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains(".field-description textarea").edit("Rounding task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await advanceTimer(840000);
    await contains("button:contains('Create')").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item:first-child").toHaveText(/24m/);
});

test.tags("desktop");
test("Timer respects manual edits, bypassing rounding and minimum", async () => {
    sessionData.timesheet_rounding_values = { minimum: 12, rounding: 12 };
    await mountWithCleanup(WebClient);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains(".field-description textarea").edit("Manual task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await advanceTimer(10000);
    await contains("div[name='unit_amount_field_container'] input").edit("00:11", {
        confirm: "Tab",
    });
    await tick();

    await contains("button:contains('Create')").click();
    await tick();

    expect(".o_att_timesheet_list .list-group-item:first-child").toHaveText(/11m/);
});

test.tags("desktop");
test("Basic checkin action", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    expect("tr[name=session-element]").toHaveCount(0, {
        message: "No seesion should have been opened",
    });
    await contains("div[name='ts_checkin_btn'] > button").click();
    await advanceTimer(625000);
    await tick();
    await contains("div[name='ts_checkin_btn'] > button").click();
    expect("tr[name=session-element]").toHaveCount(1, {
        message: "A session should have been opened",
    });
    expect("span[name='session-duration-minutes']").toHaveText("10");
    expect("span[name='session-duration-hours']").toHaveText("00");

    await contains("div[name='ts_checkin_btn'] > button").click();
    await advanceTimer(625000);
    await tick();
    await contains("div[name='ts_checkin_btn'] > button").click();
    expect("tr[name=session-element]").toHaveCount(2, {
        message: "A session should have been opened",
    });
    expect("span[name='session-total-minutes']").toHaveText("20");
    expect("span[name='session-total-hours']").toHaveText("00");
});

test("Checkin time freeze", async () => {
    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    const inputSelector = "div[name='unit_amount_field_container'] input.o_input";
    expect(inputSelector).toHaveValue("0h 0m 0s", {
        message: "Timer should start at 0",
    });
    await contains("div[name='ts_checkin_btn'] > button").click();
    await advanceTimer(6250000);
    await tick();
    await contains("div[name='ts_checkin_btn'] > button").click();
    expect(inputSelector).toHaveValue("0h 0m 0s", {
        message: "Timer should be freezed at check out",
    });
});

test.tags("desktop");
test("Timer does not add elapsed seconds to a manually set duration", async () => {
    await mountWithCleanup(WebClient);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains(".field-description textarea").edit("Manual task", {
        instantly: true,
        confirm: "Tab",
    });
    await tick();

    await selectFieldDropdownItem("project_id", "P1");
    await tick();

    await contains("div[name='unit_amount_field_container'] input").edit("08:00", {
        confirm: "Tab",
    });
    await tick();
    await advanceTimer(3000);

    await contains("button:contains('Create')").click();
    await tick();

    const [line] = pyEnv["account.analytic.line"].search_read(
        [["name", "=", "Manual task"]],
        ["unit_amount"]
    );
    expect(line.unit_amount).toBe(8);
});

test.tags("desktop");
test("Timesheet is prefilled with the task last visited", async () => {
    await mountWithCleanup(WebClient);

    setPreFilledFormTimesheet({ task_id: 1 });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "The project should be automatically filled from the visited task",
    });
    expect("div[name='task_id'] input").toHaveValue("BS task", {
        message: "The task should be filled automatically",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    setPreFilledFormTimesheet({ task_id: 2 });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='task_id'] input").toHaveValue("Another BS task", {
        message: "The last visited task should replace the one the form was prefilled with",
    });
    expect("div[name='project_id'] input").toHaveValue("Webocalypse Now", {
        message: "The project should follow the newly visited task",
    });
});

test.tags("desktop");
test("Timesheet keeps an edited draft over the task last visited", async () => {
    await mountWithCleanup(WebClient);

    setPreFilledFormTimesheet({ task_id: 1 });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    await contains(".field-description textarea").edit("Half written", {
        instantly: true,
        confirm: "Tab",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    setPreFilledFormTimesheet({ task_id: 2 });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect(".field-description textarea").toHaveValue("Half written", {
        message: "Closing the timer systray should keep the typed description as a draft",
    });
    expect("div[name='task_id'] input").toHaveValue("BS task", {
        message: "Visiting another task should not discard the draft left in the timer systray",
    });
});

test.tags("desktop");
test("Timesheet is no longer prefilled once created from the last visited task", async () => {
    await mountWithCleanup(WebClient);

    setPreFilledFormTimesheet({ task_id: 1 });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='task_id'] input").toHaveValue("BS task");

    await contains("button:contains('Create')").click();
    await tick();

    expect("div[name='task_id'] input").toHaveValue("", {
        message: "The task should not be prefilled again after a timesheet was created for it",
    });
    expect("div[name='project_id'] input").toHaveValue("", {
        message: "The project should not be prefilled again either",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='task_id'] input").toHaveValue("BS task", {
        message: "Reopening the timer systray prefills the last visited task again",
    });
});

test.tags("desktop");
test("Timesheet is no longer prefilled once the last visited task was reset away", async () => {
    await mountWithCleanup(WebClient);

    setPreFilledFormTimesheet({ task_id: 1 });

    const systrayButton = contains(
        "div.o_menu_systray button.o-dropdown i[data-icon='play_circle']"
    );
    await systrayButton.click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='task_id'] input").toHaveValue("BS task", {
        mesage: "The task should be pre-filled when opening the timer systray",
    });

    await contains("button:contains('Reset')").click();
    await tick();

    await systrayButton.click(); // Close
    await systrayButton.click(); // Re-open
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");

    expect("div[name='task_id'] input").toHaveValue("", {
        message: "Reopening the timer systray should not bring back the task the user reset away",
    });
    expect("div[name='project_id'] input").toHaveValue("", {
        message: "The project of the task the user reset away should not come back either",
    });
});

test.tags("desktop");
test("Timesheet is prefilled with project and tasks", async () => {
    onRpc("web_save", ({ args }) => {
        expect(args[1].name).toBe(false);
        expect(args[1].date).toBe(luxon.DateTime.now().toISODate());
        expect(args[1].project_id).toBe(2);
        expect(args[1].task_id).toBe(2);
    });

    setPreFilledFormTimesheet({ task_id: 2 });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        res_id: 2,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
        context: {
            active_id: 1,
        },
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains(".o_timesheet_grid_popover div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    await animationFrame();
    expect("div[name='project_id'] input").toHaveValue("Webocalypse Now", {
        message: "The project should be filled automatically",
    });
    expect("div[name='task_id'] input").toHaveValue("Another BS task", {
        message: "The task should be filled automatically",
    });
    await contains("button:contains('Create')").click();
    await tick();
});

test.tags("desktop");
test("Timer input text is fully selected when focused", async () => {
    await mountWithCleanup(WebClient);
    setPreFilledFormTimesheet({});

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    const inputSelector = "div[name='unit_amount_field_container'] input.o_input";
    const inputEl = document.querySelector(inputSelector);
    await contains(inputSelector).click();
    await animationFrame();

    expect(inputEl.selectionStart).toBe(0, {
        message: "Highlight should start at the first character",
    });
    expect(inputEl.selectionEnd).toBe(inputEl.value.length, {
        message: "Highlight should end at the last character",
    });
});

test.tags("desktop");
test("Systray total-hours color reflects working hours", async () => {
    /*
     * employee's expected working hours:
     *   - total below the working hours         -> text-danger
     *   - total at/above the working hours      -> text-success
     *   - no working hours configured (falsy 0) -> neutral
     */
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Task",
            date: "2019-03-11",
            project_id: 1,
            unit_amount: 2,
            company_id: user.activeCompany.id,
        },
    ]);

    const systrayButton = "div.o_menu_systray button.o-dropdown i[data-icon='play_circle']";
    const totalSelector = "div[name='total_hours']";
    const totalColorSelector = "div[name='total_hours'] b";

    // 1) Below the working hours (2h worked, 8h expected) -> red (danger).
    env.sessionData.timesheet_systray_employee_data.working_hours = 8;
    await contains(systrayButton).click();
    await contains("div[name='ts_checkin_btn'] > button").click();
    await animationFrame();
    expect(totalSelector).toHaveText(/Total\s*2h 00m\s*over\s*8h 00m/);
    expect(totalColorSelector).toHaveClass("text-danger", {
        message: "A total below the working hours should be red",
    });
    await contains(systrayButton).click(); // close

    // 2) At/above the working hours (2h worked, 1h expected) -> green (success).
    env.sessionData.timesheet_systray_employee_data.working_hours = 1;
    await contains(systrayButton).click();
    await animationFrame();
    expect(totalSelector).toHaveText(/Total\s*2h 00m\s*over\s*1h 00m/);
    expect(totalColorSelector).toHaveClass("text-success", {
        message: "A total exceeding the working hours should be green",
    });
    await contains(systrayButton).click(); // close

    // 3) No working hours configured (0) -> neutral
    env.sessionData.timesheet_systray_employee_data.working_hours = 0;
    await contains(systrayButton).click();
    await animationFrame();
    expect(totalSelector).toHaveText(/Total\s*2h 00m\s*over\s*0h 00m/);
    expect(totalColorSelector).not.toHaveClass("text-danger", {
        message: "With no working hours configured the total should use the normal text color",
    });
    expect(totalColorSelector).not.toHaveClass("text-success", {
        message: "With no working hours configured the total should use the normal text color",
    });
});

test("Performance: No default_get or onchange RPCs when opening new or existing timesheet forms", async () => {
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Existing Task",
            date: "2019-03-11",
            project_id: 1,
            unit_amount: 1,
            company_id: user.activeCompany.id,
        },
    ]);
    onRpc("account.analytic.line", "default_get", () => {
        expect.step("default_get");
    });
    onRpc("account.analytic.line", "onchange", () => {
        expect.step("onchange");
    });

    await mountWithCleanup(WebClient);
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();
    expect.verifySteps([], {
        message: "Opening the systray triggered an unexpected RPC.",
    });

    await contains("div[name='ts_checkin_btn'] > button").click();
    await contains(".o_att_timesheet_list .list-group-item").click();
    await tick();
    expect.verifySteps([], {
        message: "Clicking an existing timesheet triggered an unexpected RPC.",
    });
});
