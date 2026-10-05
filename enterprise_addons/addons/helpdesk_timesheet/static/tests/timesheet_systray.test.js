import { beforeEach, expect, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { advanceTime, tick } from "@odoo/hoot-mock";
import {
    contains,
    getService,
    mountWithCleanup,
    onRpc,
    selectFieldDropdownItem,
    serverState,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { setPreFilledFormTimesheet } from "@timesheet_grid/../tests/timesheet_timer_helpers";

import { defineHelpdeskTimesheetModels } from "./helpdesk_timesheet_models";
import { setupHelpdeskTimesheetEnvironment } from "@helpdesk_timesheet/../tests/helpdesk_timesheet_timer_helpers";

defineHelpdeskTimesheetModels();
const env = setupHelpdeskTimesheetEnvironment();

let pyEnv;

beforeEach(() => {
    ({ pyEnv } = env);
});

test.tags("desktop");
test("Helpdesk project toggles Task field to Ticket field and state persists on reopen", async () => {
    pyEnv["project.project"].create([
        {
            name: "Helpdesk Support Project",
            allow_timesheets: true,
            has_helpdesk_team: true,
        },
    ]);

    await mountWithCleanup(WebClient);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains("div[name='ts_checkin_btn'] > button").click();

    expect("div[name='task_id']").toHaveCount(1, {
        message: "The Task field should be visible by default",
    });
    expect("div[name='helpdesk_ticket_id']").toHaveCount(0, {
        message: "The Ticket field should be hidden by default",
    });

    await selectFieldDropdownItem("project_id", "Helpdesk Support Project");
    await tick();

    expect("div[name='task_id']").toHaveCount(0, {
        message: "The Task field should be hidden when a Helpdesk project is selected",
    });
    expect("div[name='helpdesk_ticket_id']").toHaveCount(1, {
        message: "The Ticket field should be displayed when a Helpdesk project is selected",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    await advanceTime(1000);

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    expect("div[name='project_id'] input").toHaveValue("Helpdesk Support Project");
    expect("div[name='task_id']").toHaveCount(0, {
        message: "The Task field should still be hidden",
    });
    expect("div[name='helpdesk_ticket_id']").toHaveCount(1, {
        message: "The Ticket field should still be displayed",
    });
});

test.tags("desktop");
test("Timesheet is prefilled with the task/ticket last visited", async () => {
    onRpc("/timesheet_grid/timesheet_systray_user_data", async (request) => ({
        timesheets: {
            records: [],
        },
    }));

    const [helpdeskProject] = pyEnv["project.project"].create([
        {
            name: "Helpdesk Support Project",
            allow_timesheets: true,
            has_helpdesk_team: true,
        },
    ]);
    const [firstTicket] = pyEnv["helpdesk.ticket"].create([
        {
            name: "Very persuasive ticket",
            project_id: helpdeskProject,
        },
    ]);
    const [helpdeskTask] = pyEnv["project.task"].create([
        {
            name: "Some task in an helpdesk project",
            project_id: helpdeskProject,
        },
    ]);

    setPreFilledFormTimesheet({ task_id: helpdeskTask });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        res_id: helpdeskTask,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
        context: {
            active_id: helpdeskProject,
        },
    });
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains(".o_timesheet_grid_popover div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='project_id'] input").toHaveValue("Helpdesk Support Project", {
        message: "The project should be automatically filled from the visited task",
    });
    expect("div[name='helpdesk_ticket_id'] input").toHaveValue("", {
        message: "The ticket should not be filled",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    await getService("action").doAction({
        res_model: "helpdesk.ticket",
        res_id: firstTicket,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    });
    setPreFilledFormTimesheet({ helpdesk_ticket_id: firstTicket });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();
    expect("div[name='project_id'] input").toHaveValue("Helpdesk Support Project", {
        message: "The project should follow the newly visited ticket",
    });
    expect("div[name='helpdesk_ticket_id'] input").toHaveValue("Very persuasive ticket", {
        message: "The last visited ticket should replace the task the form was prefilled with",
    });
});

test.tags("desktop");
test("Timesheet keeps an edited draft over the ticket last visited", async () => {
    onRpc("/timesheet_grid/timesheet_systray_user_data", async (request) => ({
        timesheets: {
            records: [],
        },
    }));

    const [helpdeskProject] = pyEnv["project.project"].create([
        {
            name: "Helpdesk Support Project",
            allow_timesheets: true,
            has_helpdesk_team: true,
        },
    ]);
    const [firstTicket] = pyEnv["helpdesk.ticket"].create([
        {
            name: "Very persuasive ticket",
            project_id: helpdeskProject,
        },
    ]);
    const [helpdeskTask] = pyEnv["project.task"].create([
        {
            name: "Some task in an helpdesk project",
            project_id: helpdeskProject,
        },
    ]);

    setPreFilledFormTimesheet({ task_id: helpdeskTask });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        res_id: helpdeskTask,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
        context: {
            active_id: helpdeskProject,
        },
    });
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains(".o_timesheet_grid_popover div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    await contains(".field-description textarea").edit("Half written", {
        instantly: true,
        confirm: "Tab",
    });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();

    await getService("action").doAction({
        res_model: "helpdesk.ticket",
        res_id: firstTicket,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    });
    setPreFilledFormTimesheet({ helpdesk_ticket_id: firstTicket });

    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await tick();
    expect(".field-description textarea").toHaveValue("Half written", {
        message: "Closing the timer systray should keep the typed description as a draft",
    });
    expect("div[name='helpdesk_ticket_id'] input").toHaveValue("", {
        message: "Visiting a ticket should not discard the draft left in the timer systray",
    });
});

test.tags("desktop");
test("Timesheet is prefilled with project and helpdesk ticket", async () => {
    onRpc("/timesheet_grid/timesheet_systray_user_data", async (request) => ({
        timesheets: {
            records: [],
        },
    }));

    const [helpdeskProject] = pyEnv["project.project"].create([
        {
            name: "Helpdesk Support Project",
            allow_timesheets: true,
            has_helpdesk_team: true,
        },
    ]);
    const [helpdeskTicket] = pyEnv["helpdesk.ticket"].create([
        {
            name: "Very persuasive ticket",
            project_id: helpdeskProject,
        },
    ]);

    setPreFilledFormTimesheet({ helpdesk_ticket_id: helpdeskTicket });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "helpdesk.ticket",
        res_id: helpdeskTicket,
        type: "ir.actions.act_window",
        views: [[false, "form"]],
    });
    await contains("div.o_menu_systray button.o-dropdown i[data-icon='play_circle']").click();
    await contains(".o_timesheet_grid_popover div[name='ts_checkin_btn'] > button").click();
    await waitFor(".o_timesheet_grid_popover div[name='project_id']");
    expect("div[name='project_id'] input").toHaveValue("Helpdesk Support Project", {
        message: "The project should be filled automatically",
    });
    expect("div[name='helpdesk_ticket_id'] input").toHaveValue("Very persuasive ticket", {
        message: "The ticket should be filled automatically",
    });
});

test.tags("desktop");
test("Copy existing timesheet and preserve project and ticket", async () => {
    await mountWithCleanup(WebClient);
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Old Ticket",
            date: "2019-03-11",
            project_id: 1,
            helpdesk_ticket_id: 1,
            unit_amount: 1,
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
    expect("div[name='helpdesk_ticket_id'] input").toHaveValue("Ticket 1", {
        message: "The ticket should be filled automatically",
    });
});
