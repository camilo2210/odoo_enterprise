import { beforeEach, describe, expect, test } from "@odoo/hoot";
import {
    contains,
    getService,
    mountWithCleanup,
    onRpc,
    selectFieldDropdownItem,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";
import { setupTimesheetEnvironment } from "@timesheet_grid/../tests/timesheet_timer_helpers";

import { defineHelpdeskTimesheetModels } from "./helpdesk_timesheet_models";

describe.current.tags("desktop");
defineHelpdeskTimesheetModels();

async function openAssistant() {
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "hr_timesheet_activitywatch_action",
    });
}

const env = setupTimesheetEnvironment();
let pyEnv;

beforeEach(async () => {
    ({ pyEnv } = env);
    await mountWithCleanup(WebClient);
});

test("Timesheet Assistant take a suggestion linked to a helpdesk ticket", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    const [helpdeskProject] = pyEnv["project.project"].create([
        { name: "Helpdesk Support Project", allow_timesheets: true, has_helpdesk_team: true },
    ]);
    const [ticketId] = pyEnv["helpdesk.ticket"].create([
        { name: "Very persuasive ticket", project_id: helpdeskProject },
    ]);

    // Resolve the "Task A" suggestion to the helpdesk project.
    localStorage.setItem(
        "aw_timesheet_suggestion_project_matching",
        JSON.stringify([
            {
                suggestion: "Task A",
                data: { project_id: helpdeskProject },
                datetime: today.minus({ days: 1 }).toISO(),
            },
        ])
    );

    onRpc("aw.rule", "get_applicable_rules", () => [
        {
            id: 1,
            regex: "https://test.com/(.)",
            type: "code",
            template: "Task $1",
            always_active: false,
            threshold: 0,
        },
    ]);
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 600,
            data: { title: "Any", url: "https://test.com/A" },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            [helpdeskProject]: {
                project_id: helpdeskProject,
                project_name: "Helpdesk Support Project",
                allow_timesheets: true,
            },
        },
    }));

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    await contains(".o_suggestions_suggestion").click();
    const form = ".o_activitywatch_sync_timesheet_creation_form";
    expect(form).toHaveCount(1);

    await selectFieldDropdownItem("helpdesk_ticket_id", "Very persuasive ticket");

    await contains(`${form} button[name='save_btn']`).click();
    expect(form).toHaveCount(0);

    const matches = JSON.parse(localStorage.getItem("aw_timesheet_suggestion_project_matching"));
    expect(matches.at(-1).data.helpdesk_ticket_id).toBe(ticketId);
});

test("Timesheet Assistant: should automatically link helpdesk ticket and fill form", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    const [projectId] = pyEnv["project.project"].create([
        { name: "VIP team", allow_timesheets: true, has_helpdesk_team: true },
    ]);
    const [ticketId] = pyEnv["helpdesk.ticket"].create([
        { name: "Ticket #101", project_id: projectId },
    ]);

    onRpc("account.analytic.line", "get_assistant_data", () => ({
        rounding_values: { minimum: 15, rounding: 15 },
        odoo_models_data: [
            {
                model: "helpdesk.ticket",
                label: "Ticket",
                template: "Working on $1",
                url_regex: `${window.location.origin}/odoo/helpdesk/(?:\\d+)/tickets/(\\d+)`,
                type: "odoo",
            },
        ],
    }));

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: {
                title: "Ticket #101 - Customer Issue",
                url: `${window.location.origin}/odoo/helpdesk/1/tickets/${ticketId}`,
            },
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            [projectId]: {
                project_id: projectId,
                project_name: "VIP team",
                allow_timesheets: true,
            },
        },
        "helpdesk.ticket": {
            [ticketId]: {
                project_id: projectId,
                task_id: false,
                source_record_name: "Ticket #101",
                project_name: "VIP team",
            },
        },
    }));

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText("Working on Ticket #101");

    await contains(".o_suggestions_suggestion:eq(0)").click();

    const form = ".o_activitywatch_sync_timesheet_creation_form";
    expect(form).toHaveCount(1);

    expect(
        `${form} .field-description textarea, ${form} textarea[name='name'], ${form} input[name='name']`
    ).toHaveValue("Working on Ticket #101");

    expect(`${form} .o_field_widget[name='project_id'] input`).toHaveValue("VIP team");

    expect(`${form} .o_field_widget[name='helpdesk_ticket_id'] input`).toHaveValue("Ticket #101");

    expect(`${form} .o_field_widget[name='task_id']`).toHaveCount(0);
});
