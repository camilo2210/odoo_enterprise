import { beforeEach, describe, expect, pointerDown, pointerUp, test } from "@odoo/hoot";
import { advanceTime, click, hover, keyDown, press, waitFor } from "@odoo/hoot-dom";
import { onPatched } from "@odoo/owl";
import { user } from "@web/core/user";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineStyle,
    getService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    selectFieldDropdownItem,
    serverState,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";
import { serializeDateTime } from "@web/core/l10n/dates";

import { purgeOldCacheKeys } from "@timesheet_grid/utils/timesheets_assistant";
import { TimesheetsAssistant } from "@timesheet_grid/components/aw_timesheet/aw_timesheet";
import { TimesheetAssistantModel } from "@timesheet_grid/components/aw_timesheet/aw_timesheet_model";
import { FakeEventsPlugin } from "@timesheet_grid/components/aw_timesheet/fake_events_plugin";
import { FrequencyViewerLocalConfig } from "@timesheet_grid/components/aw_timesheet/frequency_viewer/frequency_viewer_local_config";

import { defineTimesheetModels } from "./hr_timesheet_models";
import { setupTimesheetEnvironment } from "./timesheet_timer_helpers";

describe.current.tags("desktop");
defineTimesheetModels();
/* take and delete buttons are hidden, and displayed only on hover
related tests are instable, working and failing randomly when using
on hover and then click, so we force them to be visible
*/
defineStyle(`
    .o_activitywatch_sync .o_suggestions_suggestion .o_suggestions_suggestion_toolbar {
        visibility: visible !important;
        pointer-events: auto !important;
    }
    .o_activitywatch_sync .alert.alert-info.d-none.d-lg-block,
    .o_activitywatch_sync .alert.alert-warning.d-none.d-lg-block {
        display: block !important;
    }
`);

async function reload() {
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "soft_reload",
    });
}

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
    localStorage.clear();
});

test("Timesheet Assistant right panel timesheets", async () => {
    await openAssistant();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(0, {
        message: "There should be no timesheet in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
0h 00m
over
7h 36m`
    );

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
    await reload();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(1, {
        message: "There should be one timesheet in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
1h 00m
over
7h 36m`
    );

    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Test 2",
            date: "2019-03-11",
            project_id: 1,
            task_id: false,
            unit_amount: 1.5,
            company_id: user.activeCompany.id,
        },
    ]);
    await reload();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(2, {
        message: "There should be two timesheets in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
2h 30m
over
7h 36m`
    );
});
test("Timesheet Assistant right panel timesheets navigate dates", async () => {
    await openAssistant();
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Reading emails",
            date: "2019-03-11",
            project_id: 1,
            task_id: false,
            unit_amount: 1.5,
            company_id: user.activeCompany.id,
        },
        {
            user_id: serverState.userId,
            name: "Bug fixing",
            date: "2019-03-11",
            project_id: 1,
            task_id: false,
            unit_amount: 2.0,
            company_id: user.activeCompany.id,
        },
        {
            user_id: serverState.userId,
            name: "Development",
            date: "2019-03-12",
            project_id: 1,
            task_id: false,
            unit_amount: 3.25,
            company_id: user.activeCompany.id,
        },
        {
            user_id: serverState.userId,
            name: "Code review",
            date: "2019-03-12",
            project_id: 1,
            task_id: false,
            unit_amount: 1.0,
            company_id: user.activeCompany.id,
        },
        {
            user_id: serverState.userId,
            name: "Internal work",
            date: "2019-03-14",
            project_id: 1,
            task_id: false,
            unit_amount: 2.0,
            company_id: user.activeCompany.id,
        },
    ]);

    await reload();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(2, {
        message: "There should be two timesheets in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
3h 30m
over
7h 36m`
    );

    await contains(".o_calendar_button_next").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(2, {
        message: "There should be two timesheets in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
4h 15m
over
7h 36m`
    );

    await contains(".o_calendar_button_next").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(0, {
        message: "There should be no timesheet in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
0h 00m
over
7h 36m`
    );

    await contains(".o_calendar_button_next").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(1, {
        message: "There should be one timesheet in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
2h 00m
over
7h 36m`
    );

    await contains(".o_calendar_button_prev").click();
    await contains(".o_calendar_button_prev").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(2, {
        message: "There should be one timesheet in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
4h 15m
over
7h 36m`
    );

    await contains("button:contains('Today')").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(2, {
        message: "There should be two timesheets in the right panel",
    });
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
3h 30m
over
7h 36m`
    );
});

test("Timesheet Assistant right panel edit timesheet", async () => {
    await openAssistant();
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
    await reload();
    expect("div[name='timesheets_section'] > div > a > span").toHaveText("1h 00m");

    await contains("div[name='timesheets_section'] > div > a").click();
    const formSelector =
        "div[name='timesheets_section'] > div > .o_activitywatch_sync_timesheet_edition_form";
    expect(formSelector).toHaveCount(1, {
        message: "A form view should have opened where the clicked timesheet was",
    });

    await contains(`${formSelector} .field-description textarea`).edit("Test 2");
    await contains(`${formSelector} div[name='unit_amount'] input`).edit("3");
    await contains(`${formSelector} button:contains('Save')`).click();
    expect(formSelector).toHaveCount(0, {
        message: "The form should have closed",
    });
    expect("div[name='timesheets_section'] > div > a > span").toHaveText("3h 00m");
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
3h 00m
over
7h 36m`
    );
});

test("Side activity rules grouping", async () => {
    const today = "2019-03-11";
    const day = luxon.DateTime.fromISO(today);
    localStorage.setItem("aw_suggestion_pref", "project");

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: day.set({ hour: 10, minute: 0 }).toISO(),
            duration: 600,
            data: { title: "Activity A", url: "https://test.com/A" },
        },
        {
            timestamp: day.set({ hour: 10, minute: 10 }).toISO(),
            duration: 600,
            data: { title: "Activity B" },
        },
        {
            timestamp: day.set({ hour: 10, minute: 20 }).toISO(),
            duration: 600,
            data: { title: "Activity C", url: "https://test.com/C" },
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: {
                project_id: 1,
                project_name: "Project 1",
                allow_timesheets: true,
            },
            2: {
                project_id: 2,
                project_name: "Project 2",
                allow_timesheets: true,
            },
        },
    }));

    await openAssistant();

    function checkGroups(expectedGroups) {
        expect(".o_suggestions_content .list-group").toHaveCount(expectedGroups.length);
        for (const [index, group] of expectedGroups.entries()) {
            expect(
                `.o_suggestions_content div[role='heading']:eq(${index}) span:first-child`
            ).toHaveText(group.title);
            const suggestions = group.suggestions;
            expect(
                `.o_suggestions_content .list-group:eq(${index}) .o_suggestions_suggestion`
            ).toHaveCount(suggestions.length);
            for (const [sIndex, suggestion] of suggestions.entries()) {
                expect(
                    `.o_suggestions_content .list-group:eq(${index}) .o_suggestions_suggestion:eq(${sIndex})`
                ).toHaveText(suggestion);
            }
        }
    }

    checkGroups([
        { title: "Project 1", suggestions: [/Activity A/, /Activity C/] },
        { title: "Project 2", suggestions: [/Activity B/] },
    ]);

    // Case 2: A is null, B is short-lived. C should follow B because A was null.
    onRpc("aw.rule", "get_applicable_rules", () => [
        {
            id: 1,
            regex: "https://test.com/(.)",
            template: "Activity $1",
            project_id: false,
        },
        {
            id: 2,
            regex: "Activity B",
            template: "Activity B",
            project_id: [2, "Project 2"],
            side_activity: true,
        },
    ]);
    await reload();

    checkGroups([
        { title: "Project 2", suggestions: [/Activity B/, /Activity C/] },
        { title: "Unmatched", suggestions: [/Activity A/] },
    ]);
});

test("Garbage collector: purgeOldCacheKeys correctly purges old or corrupted data", async () => {
    const now = luxon.DateTime.now();
    const recentDate = now.minus({ days: 10 }).toISODate();
    const exactThresholdDate = now.minus({ days: 30 }).toISODate();
    const oldDate = now.minus({ days: 40 }).toISODate();

    const blockoutCache = {
        [recentDate]: "keep this",
        [exactThresholdDate]: "keep this too",
        [oldDate]: "delete this",
        "invalid-date-string": "delete this",
    };

    const blockoutChanges = purgeOldCacheKeys(blockoutCache, (key) => key, 30);

    expect(blockoutChanges).toBe(true, {
        message: "Should return true when old items are deleted",
    });
    expect(Object.keys(blockoutCache)).toEqual([recentDate, exactThresholdDate]);

    const recentJsonKey = JSON.stringify({ day: recentDate, id: 1 });
    const oldJsonKey = JSON.stringify({ day: oldDate, id: 2 });

    const consumedCache = {
        [recentJsonKey]: "keep",
        [oldJsonKey]: "delete",
        "corrupted-json-key{]": "delete",
    };

    const consumedChanges = purgeOldCacheKeys(consumedCache, (key) => JSON.parse(key).day, 30);

    expect(consumedChanges).toBe(true, {
        message: "Should return true when old/corrupt JSON is deleted",
    });
    expect(Object.keys(consumedCache)).toEqual([recentJsonKey]);

    const cleanCache = { [recentDate]: "keep" };

    const noChanges = purgeOldCacheKeys(cleanCache, (key) => key, 30);
    expect(noChanges).toBe(false, { message: "Should return false if nothing was purged" });
    expect(Object.keys(cleanCache)).toEqual([recentDate]);
});

test("Timesheet Assistant filters suggestions by threshold", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    localStorage.setItem("aw_suggestion_pref", "project");

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 240,
            data: { title: "Test", url: "http://localhost:8069" },
        },
    ]);
    onRpc("aw.rule", "get_applicable_rules", () => [
        {
            id: 1,
            regex: "http://localhost:8069",
            threshold: 5,
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message: "Suggestion below threshold should not be displayed",
    });

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 360,
            data: { title: "Code", url: "http://localhost:8069" },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message: "Suggestion above threshold should be displayed",
    });
});

test("Timesheet Assistant: editing then deleting a manual timesheet syncs the Chronological suggestion without crashing", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    localStorage.setItem("aw_suggestion_pref", "timeline");

    pyEnv["aw.rule"].create({
        name: "Project 1 rule",
        regex: "https://p1\\.example\\.com",
        type: "code",
        template: "Working on Project 1",
        project_id: 1,
        task_id: 1,
    });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: { title: "Coding", url: "https://p1.example.com" },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "P1", allow_timesheets: true },
        },
        "project.task": {
            1: { project_id: 1, project_name: "P1", task_id: 1, task_name: "BS task" },
        },
    }));

    // A timesheet on the same project/task already exists but was not created through the
    // assistant's "Take" button (e.g. it comes from the Grid view), so its id is not tracked
    // in "aw_assistant_timesheet_ids".
    pyEnv["account.analytic.line"].create({
        user_id: serverState.userId,
        name: "Manual entry",
        date: today.toISODate(),
        project_id: 1,
        task_id: 1,
        unit_amount: 0.1,
        company_id: user.activeCompany.id,
    });

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message:
            "opening the assistant with a pre-existing, non-assistant timesheet should not crash",
    });
    expect(".o_suggestions_suggestion_description").toHaveText("Working on Project 1");
    expect(".o_suggestions_suggestion time").toHaveText("0h 30m");
    expect("div[name='timesheets_section'] > div > a").toHaveCount(1);

    await contains("div[name='timesheets_section'] > div > a").click();
    const formSelector =
        "div[name='timesheets_section'] > div > .o_activitywatch_sync_timesheet_edition_form";
    await contains(`${formSelector} div[name='unit_amount'] input`).edit("0.4");
    await contains(`${formSelector} button:contains('Save')`).click();

    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message: "editing the manual timesheet should not crash nor remove the suggestion",
    });
    expect(".o_suggestions_suggestion time").toHaveText("0h 06m", {
        message:
            "the Chronological suggestion duration should shrink by the increase of the manual timesheet",
    });

    await contains("div[name='timesheets_section'] > div > a").click();
    await contains(`${formSelector} button:contains('Delete')`).click();

    expect("div[name='timesheets_section'] > div > a").toHaveCount(0);
    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message: "deleting the manual timesheet should not crash",
    });
    expect(".o_suggestions_suggestion time").toHaveText("0h 30m", {
        message:
            "deleting the manual timesheet should give its full duration back to the suggestion",
    });
});

test("Timesheet Assistant: a manual timesheet that fully consumes a Chronological suggestion removes it from the timeline", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    localStorage.setItem("aw_suggestion_pref", "timeline");

    pyEnv["aw.rule"].create({
        name: "Project 1 rule",
        regex: "https://p1\\.example\\.com",
        type: "code",
        template: "Working on Project 1",
        project_id: 1,
        task_id: 1,
    });

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: { title: "Coding", url: "https://p1.example.com" },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "P1", allow_timesheets: true },
        },
        "project.task": {
            1: { project_id: 1, project_name: "P1", task_id: 1, task_name: "BS task" },
        },
    }));

    pyEnv["account.analytic.line"].create({
        user_id: serverState.userId,
        name: "Manual entry",
        date: today.toISODate(),
        project_id: 1,
        task_id: 1,
        unit_amount: 0.1,
        company_id: user.activeCompany.id,
    });

    await openAssistant();
    expect(".o_suggestions_suggestion").toHaveCount(1);

    await contains("div[name='timesheets_section'] > div > a").click();
    const formSelector =
        "div[name='timesheets_section'] > div > .o_activitywatch_sync_timesheet_edition_form";
    // Raise the manual timesheet so it consumes the suggestion down to less than a minute.
    await contains(`${formSelector} div[name='unit_amount'] input`).edit("0.49");
    await contains(`${formSelector} button:contains('Save')`).click();

    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message:
            "the fully consumed suggestion should be removed from the timeline, not left behind as a stale entry",
    });
});

test("Timesheet Assistant Gmail activity", async () => {
    const now = new Date();
    localStorage.clear();

    localStorage.setItem(
        "aw_timesheet_suggestion_project_matching",
        JSON.stringify([
            {
                suggestion: "Subject E",
                data: { project_id: 2 },
                datetime: new Date(now).toISOString(),
            },
            {
                suggestion: "Subject F",
                data: { project_id: 1 },
                datetime: new Date(now).toISOString(),
            },
        ])
    );

    const events = [
        {
            // T1: Reading email (Project 1)
            timestamp: new Date(now - 2600 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg1",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner A (partnerA@example.com)",
                subject: "Subject A",
            },
        },
        {
            // T2: Random website: non key event follows previous key event
            timestamp: new Date(now - 2400 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://some-website.com",
                title: "Random Website 1",
            },
        },
        {
            // T3: Draft A (Initial state, Project 2)
            timestamp: new Date(now - 2200 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox?compose=ID_A",
                title: "Gmail - Compose",
                gmail_activity: "composing_email",
                to: ["Partner B (partnerB@example.com)"],
                subject: "Draft A - Initial",
            },
        },
        {
            // T4: Draft A (new state, will be resolved to ID_B because T5 is the next real ID in backward pass)
            timestamp: new Date(now - 2000 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
                title: "Gmail - Compose",
                gmail_activity: "composing_email",
                to: ["Partner B (partnerB@example.com)"],
                subject: "",
            },
        },
        {
            // T5: Interleaved Draft B (Project 2)
            timestamp: new Date(now - 1800 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox?compose=ID_B",
                title: "Gmail - Compose",
                gmail_activity: "composing_email",
                to: ["Partner B (partnerB@example.com)"],
                subject: "",
            },
        },
        {
            // T6: Draft A (Final state, Project 2)
            timestamp: new Date(now - 1600 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox?compose=ID_A",
                title: "Gmail - Compose",
                gmail_activity: "composing_email",
                to: [
                    "Partner A (partnerA@example.com)",
                    "Partner C (partnerC@example.com)",
                    "Recipient D (recipientD@example.com)",
                ],
                subject: "Draft A - Final",
            },
        },
        {
            // T7: Reading unknown sender, no learned frequency for "Subject D" - unmatched
            timestamp: new Date(now - 1400 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg2",
                title: "Gmail - Reading unknown sender",
                gmail_activity: "reading_email",
                from: "Unknown (unknown@example.com)",
                subject: "Subject D",
            },
        },
        {
            // T8: Random website follows last key event matched, which is Draft A - Final
            timestamp: new Date(now - 1300 * 1000).toISOString(),
            duration: 60,
            data: {
                url: "https://another-website.com",
                title: "Random Website 2",
            },
        },
        {
            // T9: Composing to Partner B, who resolves to Project 2 - but the learned
            // "Subject F" frequency (Project 1) must take priority over that.
            timestamp: new Date(now - 1100 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox?compose=ID_F",
                title: "Gmail - Compose",
                gmail_activity: "composing_email",
                to: ["Partner B (partnerB@example.com)"],
                subject: "Subject F",
            },
        },
        {
            // T10: Reading email with no recipient at all - the learned "Subject E" frequency
            // must still resolve it to Project 2, with nothing to fall back on otherwise.
            timestamp: new Date(now - 900 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg3",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                subject: "Subject E",
            },
        },
    ];

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_gmail_partners", () => ({
        "partnerA@example.com": {
            partner_name: "Partner A",
            project_id: 1,
        },
        "partnerB@example.com": {
            partner_name: "Partner B",
            project_id: 2,
        },
        "partnerC@example.com": {
            partner_name: "Partner C",
            project_id: 3,
            task_id: 1,
        },
    }));

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project 1" },
            2: { project_id: 2, project_name: "Project 2" },
            3: { project_id: 3, project_name: "Project 3" },
        },
        "project.task": {
            1: { project_id: 3, project_name: "Project 3", task_id: 1, task_name: "Task 1" },
        },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [...events].reverse());

    await openAssistant();

    await click("button[name='action_groupby_project']");
    await waitFor("button[name='action_groupby_project'].active");

    // Grouping Summary:
    // Project 1 (0h 06m):
    //   - T1 + T2 (4m): Reading email from Partner A: "Subject A"
    //   - T9 (2m): Composing email to Partner B: "Subject F" (Partner B otherwise resolves
    //     to Project 2, but the learned "Subject F" frequency takes priority)
    // Project 2 (0h 06m):
    //   - T4 + T5 (4m): Composing email to Partner B
    //   - T10 (2m): Reading email: "Subject E" (no recipient at all - matched purely by the
    //     learned "Subject E" frequency)
    // Project 3 / Task 1 (0h 05m):
    //   - T3 + T6 + T8 (5m): Composing email to Partner A, Partner C, and 1 more: "Draft A - Final"
    //     (T7 stays unmatched without impacting the next events, so T8 - a side-activity - is
    //     still attributed to the last real key event, which is "Draft A - Final")
    // Unmatched (0h 02m):
    //   - T7 (2m): Reading email from Unknown: "Subject D" (no learned frequency for "Subject D"
    //     and an unresolvable sender)

    const expected = [
        {
            title: "Project 1",
            suggestions: [
                ['Reading email from Partner A: "Subject A"', "0h 04m"],
                ['Composing email to Partner B: "Subject F"', "0h 02m"],
            ],
        },
        {
            title: "Project 2",
            suggestions: [
                ["Composing email to Partner B", "0h 04m"],
                ['Reading email: "Subject E"', "0h 02m"],
            ],
        },
        {
            title: "Project 3 / Task 1",
            suggestions: [
                [
                    'Composing email to Partner A, Partner C, and 1 more: "Draft A - Final"',
                    "0h 05m",
                ],
            ],
        },
        {
            title: "Unmatched",
            suggestions: [['Reading email from Unknown: "Subject D"', "0h 02m"]],
        },
    ];

    expect(".o_suggestions_content div[role='heading']").toHaveCount(expected.length);
    let suggestionIndex = 0;
    for (let i = 0; i < expected.length; i++) {
        const group = expected[i];
        const headingSelector = `.o_suggestions_content div[role='heading']:eq(${i})`;
        expect(`${headingSelector} span:first-child`).toHaveText(group.title);
        expect(`${headingSelector} + div .o_suggestions_suggestion`).toHaveCount(
            group.suggestions.length
        );
        for (const [text, time] of group.suggestions) {
            expect(`.o_suggestions_suggestion_description:eq(${suggestionIndex})`).toHaveText(text);
            expect(`.o_suggestions_suggestion:eq(${suggestionIndex}) time`).toHaveText(time);
            suggestionIndex++;
        }
    }
    expect(".o_suggestions_suggestion").toHaveCount(suggestionIndex);
});

test("aw_fake_events_service excludes partners without an email", async () => {
    const [noEmailPartnerId] = pyEnv["res.partner"].create([
        { name: "No Email Partner", email: false },
    ]);
    const [withEmailPartnerId] = pyEnv["res.partner"].create([
        { name: "Has Email Partner", email: "has-email@example.com" },
    ]);
    pyEnv["project.task"].write([1], { partner_id: noEmailPartnerId });
    pyEnv["project.task"].write([2], { partner_id: withEmailPartnerId });

    await reload();

    const partners = await getService(FakeEventsPlugin)._loadPartners();

    expect(partners.map((partner) => partner.id)).toEqual([withEmailPartnerId]);
});

test("Timesheet Assistant connection warning - unauthorized", async () => {
    onRpc("http://localhost:5600/api/0/buckets/*", () => {
        throw new Error("CORS failed");
    });
    onRpc("http://localhost:5600/api/0/info", (request) => {
        if (request.mode === "no-cors") {
            return new Response();
        }
    });

    await openAssistant();
    expect(".alert-info").toHaveCount(1);
    expect(".alert-info").toHaveText(
        `ActivityWatch is installed, but needs configuration.
Your browser can't connect to the tracker. Please follow these steps to configure the CORS settings.
Configure CORS`
    );
    expect(".o_activity_watch_timesheet_no_data .d-xl-none").toHaveText(
        "The Timesheets Assistant isn't available on mobile yet"
    );

    await contains(".alert-info button.btn-dark", { visible: false }).click();
    expect(".o_dialog").toHaveCount(1);
    expect(".o_dialog .h3").toHaveText("Configure CORS (Step 3 of 6)");
});

test("Timesheet Assistant connection warning - disconnected", async () => {
    onRpc("http://localhost:5600/*", () => {
        throw new Error("Disconnected");
    });

    await openAssistant();
    expect(".alert-info").toHaveCount(1);
    expect(".alert-info").toHaveText(
        `Install our activity tracker to automate your timesheet suggestions.
Already installed? Make sure ActivityWatch is running, and enable “Apps on Device” in your browser settings. \nStart Now`
    );
    expect(".o_activity_watch_timesheet_no_data .d-xl-none").toHaveText(
        "The Timesheets Assistant isn't available on mobile yet"
    );
});

test("Timesheet Assistant web watcher warning - missing", async () => {
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        window: { type: "currentwindow", id: "window", client: "aw-watcher-window" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => []);

    await openAssistant();
    expect(".alert-warning").toHaveCount(1);
    expect(".alert-warning").toHaveText(
        `Browser activity: No data detected from the extension.
We recommend installing our browser extension for more accurate suggestions. If you've already installed it, please make sure it is enabled.`
    );
});

test("Timesheet Assistant web watcher warning - inactive", async () => {
    const lastActivity = luxon.DateTime.now().minus({ minutes: 10 });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: lastActivity.toISO(),
            duration: 60,
            data: { title: "Inactive Website", url: "https://inactive.com" },
        },
    ]);

    await openAssistant();
    expect(".alert-warning").toHaveCount(1);
    expect(".alert-warning").toHaveText(
        `Browser activity: No data detected from the extension.
We recommend installing our browser extension for more accurate suggestions. If you've already installed it, please make sure it is enabled.`
    );
});

test("Timesheet Assistant masking - surfacing ActivityWatch after ignore", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    onRpc("account.analytic.line", "get_assistant_events", () => [
        {
            name: "Team Meeting",
            start: serializeDateTime(today),
            stop: serializeDateTime(today.plus({ hours: 1 })),
            duration: 3600,
            _res_model: "project.project",
            _res_id: 1,
            type: "meeting",
            isOdooModelEvent: true,
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 3600,
            data: { title: "Coding Odoo", url: "http://localhost:8069" },
        },
    ]);
    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description").toHaveText("Team Meeting");

    await contains(".o_suggestions_suggestion").click();
    await contains(".o_selection_box .btn-danger").click();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description").toHaveText("Coding Odoo");
});

test("Timesheet Assistant: deleted suggestion does not reappear after navigating away and back (timeline)", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    localStorage.setItem("aw_suggestion_pref", "timeline");

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: today.toISO(),
            duration: 3600,
            data: { title: "Coding Odoo", url: "http://localhost:8069" },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description").toHaveText("Coding Odoo");

    await contains(".o_suggestions_suggestion .o_aw_btn_remove", { visible: false }).click();
    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message: "the suggestion should be hidden right after being removed",
    });

    await contains(".o_calendar_button_next").click();
    await contains(".o_calendar_button_prev").click();
    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message: "the suggestion should still be hidden after the first navigation round-trip",
    });

    await contains(".o_calendar_button_next").click();
    await contains(".o_calendar_button_prev").click();

    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message:
            "the removed suggestion should not reappear after navigating away from and back to the day it was removed on a second time",
    });
});

test("Timesheet Assistant: deleted suggestion does not reappear after navigating away and back (project)", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    localStorage.setItem("aw_suggestion_pref", "project");

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: today.toISO(),
            duration: 3600,
            data: { title: "Coding Odoo", url: "http://localhost:8069" },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description").toHaveText("Coding Odoo");

    await contains(".o_suggestions_suggestion .o_aw_btn_remove", { visible: false }).click();
    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message: "the suggestion should be hidden right after being removed",
    });

    await contains(".o_calendar_button_next").click();
    await contains(".o_calendar_button_prev").click();
    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message: "the suggestion should still be hidden after the first navigation round-trip",
    });

    await contains(".o_calendar_button_next").click();
    await contains(".o_calendar_button_prev").click();

    expect(".o_suggestions_suggestion").toHaveCount(0, {
        message:
            "the removed suggestion should not reappear after navigating away from and back to the day it was removed on a second time",
    });
});

test("Timesheet Assistant suggestions - display actual record name", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    onRpc("account.analytic.line", "get_assistant_data", () => ({
        rounding_values: { minimum: 15, rounding: 15 },
        odoo_models_data: [
            {
                model: "project.task",
                label: "Task",
                template: "Working on $1",
                url_regex: `${window.location.origin}/odoo/tasks/(\\d+)`,
            },
        ],
    }));

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: { title: "Odoo", url: `${window.location.origin}/odoo/tasks/123` },
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", (args) => ({
        "project.task": {
            123: {
                task_id: 123,
                task_name: "Fix the Login Page",
                project_id: 1,
                project_name: "My Project",
            },
        },
    }));

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(1);
    expect(".o_suggestions_suggestion_description").toHaveText("Fix the Login Page");
});

test("Timesheet Assistant matching - frequency learning flow", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    const freqKey = "aw_timesheet_suggestion_project_matching";
    localStorage.clear();
    const day14ISO = today.minus({ days: 14 }).toISO();
    const day1ISO = today.minus({ days: 1 }).toISO();

    localStorage.setItem(
        freqKey,
        JSON.stringify([
            {
                suggestion: "Task A",
                data: { project_id: 2 },
                datetime: today.minus({ days: 40 }).toISO(),
            },
            {
                suggestion: "Task A",
                data: { project_id: 2 },
                datetime: day14ISO,
            },
            {
                suggestion: "Task A",
                data: { project_id: 2 },
                datetime: day14ISO,
            },
            {
                suggestion: "Task A",
                data: { project_id: 1 },
                datetime: day1ISO,
            },
            {
                suggestion: "Task B",
                data: { project_id: 2 },
                datetime: day1ISO,
            },
            {
                suggestion: "Task C",
                data: { project_id: 999 },
                datetime: day1ISO,
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
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 600,
            data: { title: "Any", url: "https://test.com/a" },
        },
        {
            timestamp: today.plus({ minutes: 20 }).toISO(),
            duration: 600,
            data: { title: "Any", url: "https://test.com/B" },
        },
        {
            //This event is too small to change project/task of event C
            timestamp: today.plus({ minutes: 30 }).toISO(),
            duration: 59,
            data: { title: "Any", url: "https://test.com/A" },
        },
        {
            timestamp: today.plus({ minutes: 40 }).toISO(),
            duration: 600,
            data: { title: "Any", url: "https://test.com/C" },
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project 1" },
            2: { project_id: 2, project_name: "Project 2" },
        },
    }));

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await waitFor("button[name='action_groupby_project'].active");
    expect(".o_suggestions_content div[role='heading']").toHaveCount(2);
    expect(".o_suggestions_content div[role='heading']:eq(0) span:first-child").toHaveText(
        "Project 1"
    );
    expect(".o_suggestions_content div[role='heading']:eq(1) span:first-child").toHaveText(
        "Project 2"
    );
    expect(".o_suggestions_suggestion").toHaveCount(3);

    expect(".o_suggestions_suggestion").toHaveCount(3);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText("Task a");
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText("Task B");
    expect(".o_suggestions_suggestion_description:eq(2)").toHaveText("Task C");
    await contains(".o_suggestions_suggestion .o_aw_btn_take", { visible: false }).click();
    await advanceTime(250);
    await contains(".o_suggestions_suggestion .o_aw_btn_take", { visible: false }).click();
    await advanceTime(250);

    const freq = JSON.parse(localStorage.getItem(freqKey));
    expect(freq.length).toBe(7);

    const latestMatches = freq.slice(-2);
    expect(latestMatches[0].suggestion).toBe("Task a");
    expect(latestMatches[0].data.project_id).toBe(1);
    expect(latestMatches[1].suggestion).toBe("Task B");
    expect(latestMatches[1].data.project_id).toBe(2);
    const config = new FrequencyViewerLocalConfig();
    const scores = config.scores;
    const p1Key = JSON.stringify({ project_id: 1 });
    const p2Key = JSON.stringify({ project_id: 2 });

    const now = new Date();
    const MS_PER_DAY = 1000 * 60 * 60 * 24;
    const expectedDecay14 = Math.pow(0.5, (now - new Date(day14ISO)) / MS_PER_DAY / 7);
    const expectedDecay1 = Math.pow(0.5, (now - new Date(day1ISO)) / MS_PER_DAY / 7);

    expect(Math.abs(scores["task a"][p2Key] - expectedDecay14 * 2) < 0.001).toBe(true);

    expect(Math.abs(scores["task a"][p1Key] - (expectedDecay1 + 1.0)) < 0.001).toBe(true);

    const prevScore = scores["task a"][p1Key];
    config.addMatching("Task a", { project_id: 1 });

    expect(config.scores["task a"][p1Key]).toBe(prevScore + 1);
});

test("Timesheet Assistant - small event after AFK is packed into the next activity, not AFK", async () => {
    //      Time →   -20m                 -10m      -9.5m           -8m        0
    //                |--------------------|----------|---------------|--------|
    //
    //      RAW  :                                    [Activity=======]
    //
    //      AFK  :    [AFK 600s============]
    //
    //      Unmatched:                     [Idle 30s]
    //
    // The 30s unmatched blip right after AFK is too small to stand on its own, but it is
    // immediately followed by real activity (not another AFK), so it must be packed into
    // that activity (Activity: 90 + 30 = 120s = 2 minutes) instead of being silently
    // absorbed into the AFK block (which would have inflated Away to 630s = 11 minutes).
    const now = new Date();
    pyEnv["aw.rule"].create({
        name: "Activity Rule",
        regex: "https://www.example.com/Activity",
        type: "odoo",
        template: "Activity",
    });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        afk: { type: "afkstatus", id: "afk", client: "awatcher" },
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/afk/events", () => [
        {
            timestamp: new Date(now - 20 * 60 * 1000).toISOString(),
            duration: 600,
            data: {
                status: "afk",
            },
        },
    ]);
    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: new Date(now - 10 * 60 * 1000).toISOString(),
            duration: 30,
            data: {
                title: "Idle Blip",
            },
        },
        {
            timestamp: new Date(now - 9.5 * 60 * 1000).toISOString(),
            duration: 90,
            data: {
                url: "https://www.example.com/Activity",
                title: "Activity",
            },
        },
    ]);

    const checkSuggestions = (elements) => {
        expect(".o_suggestions_suggestion").toHaveCount(elements.length);
        for (let i = 0; i < elements.length; i++) {
            expect(`.o_suggestions_suggestion_description:eq(${i})`).toHaveText(elements[i][0]);
            expect(`.o_suggestions_suggestion:eq(${i}) time`).toHaveText(elements[i][1]);
        }
    };

    await openAssistant();
    checkSuggestions([
        ["Away", "0h 10m"],
        ["Activity", "0h 02m"],
    ]);
});

test("Timesheet Assistant - Aggregate key events", async () => {
    //      Time →   -30m        -20m        -10m          -9m           -8m                 -5m        0
    //                |------------|------------|------------|------------|-------------------|----------|
    //
    //      RAW  :    [A1]         [B1]         [A2=======================]                [B3]
    //                                                       [B2===]                           [A4]
    //                                                                     [A3=]
    //
    // Filled AFK        [AFK 570s]   [AFK 570s]                                 [AFK 120s]
    //
    //          A1: 30 → 29.5
    //          B1: 20 → 19.5
    //          A2: 10 → 7
    //          B2: 9 → 8.5
    //          A3: 7 → 7.5
    //          B3: 5.5 → 5
    //          A4: 5 → 4.5

    // A1 is too small without no previous key event to merge with
    // B1 is too small and is between two afk event, it will be merged with the afk events
    // AFK 2 will be merged with previous AFK as they are similar = 20 minutes
    // A2 will be taken as key event with duration > min duration and A3 will be merged to it
    // 3 minutes + 0.5 will be rounded to 4 minutes
    // B2 intersects with A2 so will be skipped
    // B3 is too small but
    const now = luxon.DateTime.now();
    pyEnv["aw.rule"].create([
        {
            name: "Key Event A",
            regex: "https://www.example.com/A",
            type: "odoo",
            template: "Event A",
        },
        {
            name: "Key Event B",
            regex: "https://www.example.com/B",
            type: "odoo",
            template: "Event B",
        },
    ]);
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: new Date(now - 10 * 60 * 1000).toISOString(),
            duration: 3 * 60,
            data: {
                url: "https://www.example.com/A",
                title: "A2",
            },
        },
        {
            timestamp: new Date(now - 20 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/B",
                title: "B1",
            },
        },
        {
            timestamp: new Date(now - 30 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/A",
                title: "A1",
            },
        },
        {
            timestamp: new Date(now - 9 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/B",
                title: "B2",
            },
        },
        {
            timestamp: new Date(now - 7 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/A",
                title: "A3",
            },
        },
        {
            timestamp: new Date(now - 5.5 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/B",
                title: "B3",
            },
        },
        {
            timestamp: new Date(now - 5 * 60 * 1000).toISOString(),
            duration: 0.5 * 60,
            data: {
                url: "https://www.example.com/A",
                title: "A4",
            },
        },
    ]);

    const checkSuggestions = (elements) => {
        expect(".o_suggestions_suggestion").toHaveCount(elements.length);
        for (let i = 0; i < elements.length; i++) {
            expect(`.o_suggestions_suggestion_description:eq(${i})`).toHaveText(elements[i][0]);
            expect(`.o_suggestions_suggestion:eq(${i}) time`).toHaveText(elements[i][1]);
        }
    };

    await openAssistant();
    checkSuggestions([
        ["Away", "0h 20m"],
        ["Event A", "0h 04m"],
        ["Away", "0h 01m"],
        ["Event A", "0h 01m"],
    ]);
});

test("GitHub rule extracts task_id when referenced after the tag: [IMP][1]", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: {
                title: "[IMP][1] timesheet_grid: improve timesheet assistant mapping by xavierbol · Pull Request #1 · odoo/enterprise",
                url: "https://github.com/odoo/enterprise/pull/1",
            },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.task": {
            1: {
                project_id: 1,
                project_name: "timesheet_grid",
                task_id: 1,
                task_name: "Improve timesheet assistant mapping",
                allow_timesheets: true,
            },
        },
    }));

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await animationFrame();

    expect(".o_suggestions_content div[role='heading']").toHaveCount(1);
    expect(".o_suggestions_content div[role='heading']").toHaveText(
        "timesheet_grid / Improve timesheet assistant mapping\n0h 30m"
    );
    expect(".o_suggestions_suggestion_description").toHaveText(
        "[IMP] timesheet_grid: improve timesheet assistant mapping"
    );
});

test("GitHub rule extracts task_id when referenced before the tag: [1][IMP]", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: {
                title: "[1][IMP] timesheet_grid: improve timesheet assistant mapping by xavierbol · Pull Request #1 · odoo/enterprise",
                url: "https://github.com/odoo/enterprise/pull/1",
            },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.task": {
            1: {
                project_id: 1,
                project_name: "timesheet_grid",
                task_id: 1,
                task_name: "Improve timesheet assistant mapping",
                allow_timesheets: true,
            },
        },
    }));

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await animationFrame();

    expect(".o_suggestions_content div[role='heading']").toHaveCount(1);
    expect(".o_suggestions_content div[role='heading']").toHaveText(
        "timesheet_grid / Improve timesheet assistant mapping\n0h 30m"
    );
    expect(".o_suggestions_suggestion_description").toHaveText(
        "[IMP] timesheet_grid: improve timesheet assistant mapping"
    );
});

test("GitHub rule does not extract task_id when the PR has no numeric tag", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: {
                title: "[IMP] timesheet_grid: improve timesheet assistant mapping by odooUnicorn · Pull Request #1 · odoo/enterprise",
                url: "https://github.com/odoo/enterprise/pull/1",
            },
        },
    ]);

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await animationFrame();

    expect(".o_suggestions_content div[role='heading']").toHaveCount(1);
    expect(".o_suggestions_content div[role='heading']").toHaveText("Unmatched\n0h 30m");
    expect(".o_suggestions_suggestion_description").toHaveText(
        "[IMP] timesheet_grid: improve timesheet assistant mapping"
    );
});

test("Timesheet Assistant hides Add button when allow_timesheets is false", async () => {
    const now = new Date();
    localStorage.clear();

    const events = [
        {
            timestamp: new Date(now - 1200 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg1",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner Blocked (blocked@example.com)",
                subject: "Blocked Project Request",
            },
        },
        {
            timestamp: new Date(now - 600 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg2",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner Allowed (allowed@example.com)",
                subject: "Allowed Project Request",
            },
        },
    ];

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_gmail_partners", () => ({
        "blocked@example.com": {
            partner_name: "Partner Blocked",
            project_id: 1,
        },
        "allowed@example.com": {
            partner_name: "Partner Allowed",
            project_id: 2,
        },
    }));

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project Blocked", allow_timesheets: false },
            2: { project_id: 2, project_name: "Project Allowed", allow_timesheets: true },
        },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [...events].reverse());

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await waitFor("button[name='action_groupby_project'].active");

    expect(".o_suggestions_content div[role='heading']").toHaveCount(2);

    expect(".o_suggestions_content div[role='heading']:eq(0) span:first-child").toHaveText(
        "Project Blocked"
    );

    expect(".o_suggestions_suggestion:eq(0) .o_aw_btn_take").toHaveCount(0, {
        message: "Add button should be hidden when allow_timesheets is false",
    });

    expect(".o_suggestions_suggestion:eq(0) .o_aw_btn_remove").toHaveCount(1);

    expect(".o_suggestions_content div[role='heading']:eq(1) span:first-child").toHaveText(
        "Project Allowed"
    );

    expect(".o_suggestions_suggestion:eq(1) .o_aw_btn_take").toHaveCount(1, {
        message: "Add button should be visible when allow_timesheets is true",
    });
    expect(".o_suggestions_suggestion:eq(1) .o_aw_btn_remove").toHaveCount(1);
});

test("Timesheet Assistant: afk events", async () => {
    //     Time →   -115m        -60m        -55m        -50m        -10m        -5m         0
    //           |------------|------------|------------|------------|------------|------|
    //
    // WEB  :    |=========================|                                                    (event 1: 115m → 55m)
    //                                      |-|                                                 (event 2: 54.5m, 1m)
    //                                                                            |==|          (event 3: 5m → 3m)
    //                                                                                 |-|      (event 4: 1m → now)
    //
    // AFK  :                              |======================================|             (event 1: 55m → 5m)
    //                                        |-|                                               (event 2: fully inside, ignored)
    //                                                  |-|                                     (event 3: inside, ignored)
    //                                                                        |====|            (event 4: 6m → 4m)
    //
    //
    //
    //          -115m                    -55m                                     5m  4m  3m         1m  now
    // Result:   |=======WEB===============|=========AFK==========================|AFK|WEB|AFK Filled|WEB|

    pyEnv["aw.rule"].create([
        {
            name: "Test Rule",
            regex: "https://www.example.com*",
            type: "odoo",
            template: "Odoo Test",
            project_id: 1,
            task_id: 1,
        },
        {
            name: "Test Rule 2",
            regex: "https://www.example2.com*",
            type: "odoo",
            template: "Odoo Test 2",
            project_id: 1,
            task_id: 1,
        },
    ]);
    const now = new Date();
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        afk: { type: "afkstatus", id: "afk", client: "awatcher" },
        web: { type: "web.tab.current", id: "web", client: "aw-client-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: new Date(now - 115 * 60 * 1000).toISOString(),
            duration: 3600,
            data: {
                url: "https://www.example.com",
                title: "Example",
            },
        },
        {
            //Test key event during afk event overlap to make sure they still don't appear
            timestamp: new Date(now - 54.5 * 60 * 1000).toISOString(),
            duration: 60,
            data: {
                url: "https://www.example2.com",
                title: "Example",
            },
        },
        {
            //Test key event get cut off by afk event
            timestamp: new Date(now - 5 * 60 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://www.example2.com",
                title: "Example",
            },
        },
        {
            //Creat gap to make a afk filler event
            timestamp: new Date(now - 60 * 1000).toISOString(),
            duration: 60,
            data: {
                url: "https://www.example.com",
                title: "Example",
            },
        },
    ]);
    onRpc("http://localhost:5600/api/0/buckets/afk/events", () => [
        {
            timestamp: new Date(now - 55 * 60 * 1000).toISOString(),
            duration: 50 * 60,
            data: {
                status: "afk",
            },
        },
        {
            //Test overlapping afk events that a totaly replace by previous
            timestamp: new Date(now - 54 * 60 * 1000).toISOString(),
            duration: 60,
            data: {
                status: "afk",
            },
        },
        {
            timestamp: new Date(now - 50 * 60 * 1000).toISOString(),
            duration: 60,
            data: {
                status: "afk",
            },
        },
        {
            //Test akf event that extend beyond previous
            timestamp: new Date(now - 6 * 60 * 1000).toISOString(),
            duration: 120,
            data: {
                status: "afk",
            },
        },
    ]);
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project", allow_timesheets: true },
        },
        "project.task": {
            1: { task_id: 1, task_name: "Task", allow_timesheets: true },
        },
    }));
    await openAssistant();
    await click("button[name='action_groupby_project']");
    await waitFor("button[name='action_groupby_project'].active");
    expect(".o_suggestions_content div[role='heading']").toHaveCount(1);
    expect(".o_suggestions_content .o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_content .o_suggestions_suggestion i[data-icon='dark_mode']").toHaveCount(
        0
    );
    await click("button[name='action_groupby_timeline']");
    await waitFor("button[name='action_groupby_timeline'].active");
    expect(".o_suggestions_content div[role='heading']").toHaveCount(0);
    expect(".o_suggestions_content .o_suggestions_suggestion").toHaveCount(5);
    expect(".o_suggestions_content .o_suggestions_suggestion i[data-icon='dark_mode']").toHaveCount(
        2
    );

    const checkSuggestions = (elements) => {
        expect(".o_suggestions_suggestion").toHaveCount(elements.length);
        for (let i = 0; i < elements.length; i++) {
            expect(`.o_suggestions_suggestion_description:eq(${i})`).toHaveText(elements[i][0]);
            expect(`.o_suggestions_suggestion:eq(${i}) time`).toHaveText(elements[i][1]);
        }
    };

    checkSuggestions([
        ["Odoo Test", "1h 00m"],
        ["Away", "0h 51m"],
        ["Odoo Test 2", "0h 01m"],
        ["Away", "0h 02m"],
        ["Odoo Test", "0h 01m"],
    ]);
});

test("Timesheet Assistant: always active events block afk", async () => {
    // Time →   -40m        -35m        -30m        -25m        -20m        -15m        -10m         0
    //           |------------|------------|------------|------------|------------|------------|------|
    //
    // ACTIVE :  |============|
    //                                     |=========================|
    //
    // AFK    :               |============|
    //                                                                            |============|
    //
    // NOT ACT:                                                      |============|
    //                                                                                          |======|
    //
    //          -40         -35                               -30          -20           -15     -10            now
    // Result:   |===Active===|AFK precedded by Active so Active|===Active==|==Not Active|===AFK==|==Not Active==|
    const now = new Date();
    pyEnv["aw.rule"].create([
        {
            name: "Always Active Rule",
            regex: "https://www.example.com*",
            type: "odoo",
            template: "Always Active",
            always_active: true,
        },
        {
            name: "Not Always Active Rule",
            regex: "https://www.example2.com*",
            type: "odoo",
            template: "Not Always Active",
            always_active: false,
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        afk: { type: "afkstatus", id: "afk", client: "awatcher" },
        web: { type: "web.tab.current", id: "web", client: "aw-client-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: new Date(now - 40 * 60 * 1000).toISOString(),
            duration: 5 * 60,
            data: {
                url: "https://www.example.com",
                title: "Always Active",
            },
        },
        {
            timestamp: new Date(now - 30 * 60 * 1000).toISOString(),
            duration: 10 * 60,
            data: {
                url: "https://www.example.com",
                title: "Always Active",
            },
        },
        {
            timestamp: new Date(now - 20 * 60 * 1000).toISOString(),
            duration: 5 * 60,
            data: {
                url: "https://www.example2.com",
                title: "Not Always Active",
            },
        },
        {
            timestamp: new Date(now - 10 * 60 * 1000).toISOString(),
            duration: 10 * 60,
            data: {
                url: "https://www.example2.com",
                title: "Not Always Active",
            },
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/afk/events", () => [
        {
            timestamp: new Date(now - 35 * 60 * 1000).toISOString(),
            duration: 5 * 60,
            data: {
                status: "afk",
            },
        },
        {
            timestamp: new Date(now - 15 * 60 * 1000).toISOString(),
            duration: 5 * 60,
            data: {
                status: "afk",
            },
        },
    ]);

    await openAssistant();
    expect(".o_suggestions_content .o_suggestions_suggestion").toHaveCount(4);

    const checkSuggestions = (elements) => {
        expect(".o_suggestions_suggestion").toHaveCount(elements.length);
        for (let i = 0; i < elements.length; i++) {
            expect(`.o_suggestions_suggestion_description:eq(${i})`).toHaveText(elements[i][0]);
            expect(`.o_suggestions_suggestion:eq(${i}) time`).toHaveText(elements[i][1]);
        }
    };

    checkSuggestions([
        ["Always Active", "0h 20m"],
        ["Not Always Active", "0h 05m"],
        ["Away", "0h 05m"],
        ["Not Always Active", "0h 10m"],
    ]);
});

test("Timesheet Assistant hover auto select", async () => {
    const fakeService = getService(FakeEventsPlugin);
    const today = luxon.DateTime.now().startOf("day").toISO().split("T")[0];
    const start1 = luxon.DateTime.fromISO(`${today}T10:00:00Z`);
    const start2 = luxon.DateTime.fromISO(`${today}T11:00:00Z`);
    const start3 = luxon.DateTime.fromISO(`${today}T12:00:00Z`);
    localStorage.setItem("aw_suggestion_pref", "timeline");
    fakeService.cache[today] = {
        fakeEvents: {
            currentwindow: [
                {
                    timestamp: start1.toISO(),
                    duration: 3600,
                    start: start1,
                    stop: start1.plus({ seconds: 3600 }),
                    type: "code",
                    data: { app: "Terminal", title: "Terminal" },
                },
            ],
            "web.tab.current": [
                {
                    timestamp: start2.toISO(),
                    duration: 3600,
                    start: start2,
                    stop: start2.plus({ seconds: 3600 }),
                    type: "reading_email",
                    data: { app: "Chrome", title: "Inbox", url: "https://mail.google.com" },
                },
                {
                    timestamp: start3.toISO(),
                    duration: 3600,
                    start: start3,
                    stop: start3.plus({ seconds: 3600 }),
                    type: "word",
                    data: { app: "Chrome", title: "Meeting Notes", url: "https://docs.google.com" },
                },
            ],
        },
        partnerEmails: new Set(),
    };
    await openAssistant();

    const getSuggestion = (index) => document.querySelectorAll(".o_suggestions_suggestion")[index];

    // Click on the first suggestion
    await pointerDown(getSuggestion(0));
    await animationFrame();
    expect(getSuggestion(0)).toHaveClass("o_isSelected", {
        message: "The first item should be selected after the initial press on the mouse button",
    });
    expect("textarea.o_input").toHaveValue("Terminal", {
        message: "A form view should have opened with the clicked suggestion",
    });
    // Hover over the second suggestion, with the button still pressed
    await hover(getSuggestion(1));
    await animationFrame();
    expect(getSuggestion(1)).toHaveClass("o_isSelected", {
        message: "The second item should be selected after the hover",
    });
    expect("textarea.o_input").toHaveValue("Terminal", {
        message: "The form view should not have been updated",
    });
    // Hover over the third suggestion, with the button still pressed
    await hover(getSuggestion(2));
    await animationFrame();
    expect(getSuggestion(2)).toHaveClass("o_isSelected", {
        message: "The third item should be selected after the hover",
    });
    // Hover over the second suggestion, with the button still pressed, and the suggestion selected
    await hover(getSuggestion(1));
    await animationFrame();
    expect(getSuggestion(1)).not.toHaveClass("o_isSelected", {
        message: "The second item should be unselected after the hover",
    });
    // Hover over the first suggestion, and release the mouse button
    await pointerUp(getSuggestion(0));
    await animationFrame();
    expect(getSuggestion(0)).not.toHaveClass("o_isSelected", {
        message: "The first item should be unselected after the release of the mouse button",
    });
    expect("textarea.o_input").toHaveValue("Meeting Notes", {
        message: "The form view should have been updated",
    });
    // Hover over the second suggestion, without pressing the button
    await hover(getSuggestion(1));
    await animationFrame();
    expect(getSuggestion(1)).not.toHaveClass("o_isSelected", {
        message: "The second item state should not change after the hover",
    });
    // click on the 3rd suggestion & maintain the mouse button clicked, the current form should be removed
    await pointerDown(getSuggestion(2));
    await animationFrame();
    expect(getSuggestion(2)).not.toHaveClass("o_isSelected", {
        message: "The 3rd item state should switch to not selected",
    });
    expect("textarea.o_input").toHaveCount(0, {
        message: "No suggestion are selected, the view form should be removed",
    });
    // hover the 2nd suggestion & check that the current form is displayed again
    await hover(getSuggestion(1));
    await animationFrame();
    expect(getSuggestion(1)).toHaveClass("o_isSelected", {
        message: "The second item should be selected after the hover",
    });
    expect("textarea.o_input").toHaveValue("Inbox", {
        message: "The form view should have been updated",
    });
});

test("Timesheet Assistant Suggestions Section View", async () => {
    const now = new Date();
    const events = [
        // Unmatched (13m + 18m = 31m)
        {
            timestamp: new Date(now - 11980 * 1000).toISOString(),
            duration: 12 * 60 + 50,
            data: {
                title: "Inbox - Gmail",
                url: "https://mail.google.com/mail/u/0",
            },
        },
        {
            timestamp: new Date(now - 11210 * 1000).toISOString(),
            duration: 18 * 60 + 10,
            data: {
                title: "Slack - General Channel",
                url: "https://app.slack.com/client",
            },
        },

        // Project 1: 1m + 1m + 1m = 3m
        {
            timestamp: new Date(now - 10120 * 1000).toISOString(),
            duration: 80,
            data: {
                title: "P1 Task 1",
                url: "https://p1.com/1",
            },
        },
        {
            timestamp: new Date(now - 10060 * 1000).toISOString(),
            duration: 80,
            data: {
                title: "P1 Task 2",
                url: "https://p1.com/2",
            },
        },
        {
            timestamp: new Date(now - 9980 * 1000).toISOString(),
            duration: 80,
            data: {
                title: "P1 Task 3",
                url: "https://p1.com/3",
            },
        },

        // Project 2: 29m + 34m = 1h 03m
        {
            timestamp: new Date(now - 9900 * 1000).toISOString(),
            duration: 29 * 60 + 15,
            data: {
                title: "P2 Task 1",
                url: "https://p2.com/1",
            },
        },
        {
            timestamp: new Date(now - 8160 * 1000).toISOString(),
            duration: 34 * 60 + 20,
            data: {
                title: "P2 Task 2",
                url: "https://p2.com/2",
            },
        },

        // Project 3: 16m + 22m + 46m = 1h 24m
        {
            timestamp: new Date(now - 6120 * 1000).toISOString(),
            duration: 15 * 60 + 45,
            data: {
                title: "P3 Task 1",
                url: "https://p3.com/1",
            },
        },
        {
            timestamp: new Date(now - 5400 * 1000).toISOString(),
            duration: 22 * 60 + 10,
            data: {
                title: "P3 Task 2",
                url: "https://p3.com/2",
            },
        },
        {
            timestamp: new Date(now - 4080 * 1000).toISOString(),
            duration: 45 * 60 + 30,
            data: {
                title: "P3 Task 3",
                url: "https://p3.com/3",
            },
        },
    ];

    onRpc("aw.rule", "get_applicable_rules", () => [
        {
            id: 1,
            regex: "^(.*?)\\|https://p1\\.com",
            type: "code",
            template: "$1",
            project_id: [1],
            always_active: false,
        },
        {
            id: 2,
            regex: "^(.*?)\\|https://p2\\.com",
            type: "code",
            template: "$1",
            project_id: [2],
            always_active: false,
        },
        {
            id: 3,
            regex: "^(.*?)\\|https://p3\\.com",
            type: "code",
            template: "$1",
            project_id: [3],
            always_active: false,
        },
        {
            id: 4,
            regex: "mail\\.google\\.com",
            type: "communication",
            template: "Checking Emails",
            always_active: false,
        },
        {
            id: 5,
            regex: "app\\.slack\\.com",
            type: "communication",
            template: "Team Chat",
            always_active: false,
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project 1" },
            2: { project_id: 2, project_name: "Project 2" },
            3: { project_id: 3, project_name: "Project 3" },
        },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [...events].reverse());

    await openAssistant();
    await click("button[name='action_groupby_project']");
    await waitFor("button[name='action_groupby_project'].active");

    expect(".o_suggestions_suggestion").toHaveCount(10, {
        message: "There should be 10 suggestions in By Project view.",
    });
    expect("div[role='heading'][aria-level='3']").toHaveCount(4, {
        message: "There should be 4 suggestion groups (3 projects + 1 unmatched)",
    });

    const expectedTimes = [
        { label: "Project 1", time: "0h 03m" },
        { label: "Project 2", time: "1h 03m" },
        { label: "Project 3", time: "1h 24m" },
        { label: "Unmatched", time: "0h 31m" },
    ];

    for (const [i, { label, time }] of expectedTimes.entries()) {
        expect(`div[role='heading'][aria-level='3']:eq(${i}) time`).toHaveText(time, {
            message: `${label} should sum exactly to ${time}`,
        });
    }

    expect(".o_suggestions_content .position-sticky.bottom-0").toHaveText(
        `Total
3h 01m
over
7h 36m`
    );

    //No Group by - Chronological Order
    await contains("button", { text: "Chronological" }).click();
    expect(".o_suggestions_suggestion").toHaveCount(10, {
        message: "There should be 10 suggestions in Chronological View",
    });

    expect(".o_suggestions_content .position-sticky.bottom-0").toHaveText(
        `Total
3h 01m
over
7h 36m`
    );

    await contains(".o_suggestions_suggestion:contains('P3 Task 3')").click();
    await contains(".o_selection_box .btn-danger").click();
    expect(".o_suggestions_suggestion").toHaveCount(9, {
        message: "There should be 9 suggestions after deletion",
    });

    expect(".o_suggestions_content .position-sticky.bottom-0").toHaveText(
        `Total
2h 15m
over
7h 36m`
    );
});

test("Timesheet Assistant: Discord rule merges channel suggestions from the same template", async () => {
    const today = luxon.DateTime.now().startOf("day");

    pyEnv["aw.rule"].create({
        name: "Discord Channel",
        regex:
            "(?:#(.*?)\\s*\\|\\s*(.*?)\\s*-\\s*Discord)|" +
            "(?:(?:\\(\\d+\\)\\s)?Discord\\s\\|\\s#(.*?)\\s\\|\\s(.*?)\\|https:\\/\\/discord\\.com\\/channels\\/.*)",
        type: "messaging",
        template: "Discussing in channel: #$1 ($2)",
        always_active: false,
    });

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        window: { type: "currentwindow", id: "window", client: "aw-watcher-window" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/window/events", () => [
        {
            timestamp: today.plus({ hours: 9 }).toISO(),
            duration: 1800,
            data: { title: "#timesheets-assistant | Odoo - Discord" },
        },
        {
            timestamp: today.plus({ hours: 9, minutes: 30 }).toISO(),
            duration: 1800,
            data: { title: "#general | TeamChat - Discord" },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText(
        "Discussing in channel: #timesheets-assistant (Odoo)"
    );
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText(
        "Discussing in channel: #general (TeamChat)"
    );

    await contains(".o_suggestions_suggestion:eq(0)").click();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Discussing in channel: #timesheets-assistant (Odoo)"
    );

    await contains(".o_suggestions_suggestion:eq(1)").click();
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Discussing in channel: #timesheets-assistant and general (Odoo and TeamChat)"
    );
});

test("Timesheet Assistant: merge descriptions for Discord DM from the same template", async () => {
    const today = luxon.DateTime.now().startOf("day");

    pyEnv["aw.rule"].create({
        name: "Discord DM",
        regex:
            "(?:@(.*?)\\s*-\\s*Discord)|" +
            "(?:(?:\\(\\d+\\)\\s)?Discord\\s\\|\\s@(.*?)\\|https:\\/\\/discord\\.com\\/channels\\/.*)",
        type: "communication",
        template: "Discussing with @$1",
        always_active: false,
    });

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        window: { type: "currentwindow", id: "window", client: "aw-watcher-window" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/window/events", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: { title: "@Marc Demo - Discord" },
        },
        {
            timestamp: today.plus({ hours: 14 }).toISO(),
            duration: 1800,
            data: { title: "@Brandon Freeman - Discord" },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(3);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText("Discussing with @Marc Demo");
    expect(".o_suggestions_suggestion_description:eq(2)").toHaveText(
        "Discussing with @Brandon Freeman"
    );

    await contains(".o_suggestions_suggestion:eq(0)").click();
    await contains(".o_suggestions_suggestion:eq(2)").click();
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Discussing with @Marc Demo and Brandon Freeman"
    );
});

test("Timesheet Assistant: merge Google Docs suggestions that has the same template", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    pyEnv["aw.rule"].create({
        name: "Google Docs",
        regex: "(.*) - Google Docs\\|https:\\/\\/docs\\.google\\.com",
        type: "word",
        template: "Working on $1",
        always_active: false,
    });

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: today.toISO(),
            duration: 1800,
            data: {
                title: "Meeting Notes - Google Docs",
                url: "https://docs.google.com/document/d/1",
            },
        },
        {
            timestamp: today.plus({ minutes: 30 }).toISO(),
            duration: 1800,
            data: {
                title: "User Feedback Summary - Google Docs",
                url: "https://docs.google.com/document/d/2",
            },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText("Working on Meeting Notes");
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText(
        "Working on User Feedback Summary"
    );

    await contains(".o_suggestions_suggestion:eq(0)").click();
    await contains(".o_suggestions_suggestion:eq(1)").click();
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Working on Meeting Notes and User Feedback Summary"
    );
});

test("Timesheet Assistant: merge Gmail suggestions that has the same template", async () => {
    const now = new Date();

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_gmail_partners", () => ({
        "partnerA@example.com": { partner_name: "Partner A" },
        "partnerB@example.com": { partner_name: "Partner B" },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: new Date(now - 1000 * 1000).toISOString(),
            duration: 600,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg1",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner A (partnerA@example.com)",
                subject: "Subject A",
            },
        },
        {
            timestamp: new Date(now - 400 * 1000).toISOString(),
            duration: 600,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg2",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner B (partnerB@example.com)",
                subject: "Subject B",
            },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText(
        'Reading email from Partner A: "Subject A"'
    );
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText(
        'Reading email from Partner B: "Subject B"'
    );

    await contains(".o_suggestions_suggestion:eq(0)").click();
    await contains(".o_suggestions_suggestion:eq(1)").click();
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        'Reading email from Partner A and Partner B: "Subject A and Subject B"'
    );
});

test("Timesheet Assistant: should merge the descriptions for Working on template rule", async () => {
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });
    const timesheetsUrl = `${window.location.origin}/odoo/timesheets`;

    onRpc("account.analytic.line", "get_assistant_data", () => ({
        odoo_models_data: [
            {
                model: "project.task",
                label: "Task",
                template: "Working on $1",
                url_regex: `${window.location.origin}/odoo/tasks/(\\d+)`,
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
            data: { title: "Timesheets", url: timesheetsUrl },
        },
        {
            timestamp: today.plus({ minutes: 30 }).toISO(),
            duration: 1800,
            data: {
                title: "Task",
                url: `${window.location.origin}/odoo/tasks/10`,
            },
        },
    ]);
    onRpc("account.analytic.line", "get_aw_app_from_urls", () => ({
        [timesheetsUrl]: { app_name: "Timesheets" },
    }));
    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({}));

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText("Working on Timesheets");
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText("Working on Task");

    await contains(".o_suggestions_suggestion:eq(0)").click();
    await contains(".o_suggestions_suggestion:eq(1)").click();
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Working on Timesheets and Task"
    );
});

test("Timesheet Assistant total-hours color reflects working hours (right panel & suggestions)", async () => {
    localStorage.clear();
    /*
     * employee's expected working hours:
     *   - total below the working hours         -> text-danger
     *   - total at/above the working hours      -> text-success
     *   - no working hours configured (falsy 0) -> neutral
     */
    let workingHours = 7.6; // 7h 36m
    onRpc("account.analytic.line", "get_aw_timesheet_data", ({ args }) => {
        const [date] = args;
        const specification =
            pyEnv["account.analytic.line"]._get_aw_timesheet_fields_specification();
        const domain = [
            ["date", "=", date],
            ["user_id", "=", serverState.userId],
        ];
        return {
            working_hours: workingHours,
            specification,
            timesheets: pyEnv["account.analytic.line"].web_search_read(domain, specification),
        };
    });

    // Right panel: a single 3h timesheet.
    pyEnv["account.analytic.line"].create([
        {
            user_id: serverState.userId,
            name: "Timesheet",
            date: "2019-03-11",
            project_id: 1,
            task_id: false,
            unit_amount: 3,
            company_id: user.activeCompany.id,
        },
    ]);

    // Suggestions: a single unmatched 2h browser activity.
    const now = new Date();
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [
        {
            timestamp: new Date(now - 7200 * 1000).toISOString(),
            duration: 7200,
            data: { title: "Research", url: "https://example.com/research" },
        },
    ]);

    const rightPanel = ".o_activity_watch_timesheet_right_tots";
    const suggestions = ".o_suggestions_content .position-sticky.bottom-0";

    await openAssistant();

    // Sanity: both totals are rendered with the expected durations.
    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message: "The 2h browser activity should produce a single suggestion",
    });
    expect(rightPanel).toHaveText(
        `Total
3h 00m
over
7h 36m`
    );
    expect(suggestions).toHaveText(
        `Total
2h 00m
over
7h 36m`
    );

    // 1) Below the working hours -> red (danger).
    expect(`${rightPanel} b`).toHaveClass("text-danger", {
        message: "Right panel: a total below the working hours should be red",
    });
    expect(`${suggestions} b`).toHaveClass("text-danger", {
        message: "Suggestions: a total below the working hours should be red",
    });

    // 2) At/above the working hours -> green (success).
    workingHours = 1; // 1h, below both the 3h panel total and the 2h suggestions total
    await reload();
    expect(rightPanel).toHaveText(
        `Total
3h 00m
over
1h 00m`
    );
    expect(suggestions).toHaveText(
        `Total
2h 00m
over
1h 00m`
    );
    expect(`${rightPanel} b`).toHaveClass("text-success", {
        message: "Right panel: a total exceeding the working hours should be green",
    });
    expect(`${suggestions} b`).toHaveClass("text-success", {
        message: "Suggestions: a total exceeding the working hours should be green",
    });

    // 3) No working hours configured (falsy) -> neutral.
    workingHours = 0;
    await reload();
    expect(rightPanel).toHaveText(
        `Total
3h 00m
over
0h 00m`
    );
    expect(suggestions).toHaveText(
        `Total
2h 00m
over
0h 00m`
    );
    for (const sel of [`${rightPanel} b`, `${suggestions} b`]) {
        expect(sel).not.toHaveClass("text-danger", {
            message: "With no working hours configured the total should use the normal text color",
        });
        expect(sel).not.toHaveClass("text-success", {
            message: "With no working hours configured the total should use the normal text color",
        });
    }
});

const testKeyboardNavigation = async (viewMode) => {
    const fakeService = getService(FakeEventsPlugin);
    const today = luxon.DateTime.now().startOf("day").toISO().split("T")[0];
    const start1 = luxon.DateTime.fromISO(`${today}T10:00:00Z`);
    const start2 = luxon.DateTime.fromISO(`${today}T11:00:00Z`);
    const start3 = luxon.DateTime.fromISO(`${today}T12:00:00Z`);
    localStorage.setItem("aw_suggestion_pref", viewMode);
    fakeService.cache[today] = {
        fakeEvents: {
            currentwindow: [
                {
                    timestamp: start1.toISO(),
                    duration: 1800,
                    start: start1,
                    stop: start1.plus({ seconds: 1800 }),
                    type: "code",
                    data: { app: "Terminal", title: "Terminal" },
                },
            ],
            "web.tab.current": [
                {
                    timestamp: start2.toISO(),
                    duration: 1800,
                    start: start2,
                    stop: start2.plus({ seconds: 1800 }),
                    type: "reading_email",
                    data: { app: "Chrome", title: "Inbox" },
                },
                {
                    timestamp: start3.toISO(),
                    duration: 1800,
                    start: start3,
                    stop: start3.plus({ seconds: 1800 }),
                    type: "word",
                    data: { app: "Chrome", title: "Meeting Notes" },
                },
            ],
        },
        partnerEmails: new Set(),
    };
    const getSuggestion = (index) => document.querySelectorAll(".o_suggestions_suggestion")[index];

    await openAssistant();
    await animationFrame();
    await click(".o_suggestions");
    await animationFrame();

    await press("ArrowDown");
    await animationFrame();
    await press("ArrowDown");
    await animationFrame();

    expect(getSuggestion(1)).toHaveClass("o_keyboard_focused", {
        message: "The second item should have visual focus",
    });

    await press("Space");
    await animationFrame();

    expect(getSuggestion(1)).toHaveClass("o_isSelected", {
        message: "The second item should be selected after Space",
    });
    expect(".o_activitywatch_sync_timesheet_creation_form").toHaveCount(0, {
        message: "Form should remain closed when selecting with Space",
    });

    await keyDown("Shift");
    await press("ArrowDown");
    await animationFrame();

    expect(getSuggestion(2)).toHaveClass("o_keyboard_focused", {
        message: "The third item should have visual focus",
    });
    expect(getSuggestion(1)).toHaveClass("o_isSelected", {
        message: "The second item should remain selected",
    });
    expect(getSuggestion(2)).toHaveClass("o_isSelected", {
        message: "The third item should now be selected",
    });

    await press("Enter");
    await animationFrame();

    expect(".o_activitywatch_sync_timesheet_creation_form").toHaveCount(1, {
        message: "Form should be open after clicking the item",
    });

    await press("Escape");
    await animationFrame();
};

test("Timesheet Assistant keyboard navigation - Timeline", async () => {
    await testKeyboardNavigation("timeline");
});

test("Timesheet Assistant keyboard navigation - Project", async () => {
    await testKeyboardNavigation("project");
});

test("Timesheet Assistant respects duration", async () => {
    await openAssistant();
    const startDatetime = luxon.DateTime.fromISO("2025-01-22T08:00:00");
    const endDatetime = luxon.DateTime.fromISO("2025-01-22T17:00:00");

    onRpc("account.analytic.line", "get_assistant_events", () => [
        {
            name: "Opera Project",
            start: serializeDateTime(startDatetime),
            stop: serializeDateTime(endDatetime),
            duration: 6, // allocated_hours = 6 overrides the 9h time span
            _res_model: "project.project",
            _res_id: 1,
            type: "meeting",
            isOdooModelEvent: true,
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Opera Project" },
        },
    }));
    await reload();

    expect(".o_suggestions_suggestion").toHaveCount(1, {
        message: "Expected exactly one suggestion to be returned",
    });
    expect(".o_suggestions_suggestion_description").toHaveText("Opera Project");
    // Verify allocated hours duration (6h 00m) is respected instead of full slot time (9h 00m)
    expect(".o_suggestions_suggestion time").toHaveText("6h 00m", {
        message: "The event duration should be computed from allocated_hours (6h)",
    });
});

test("Timesheet Assistant chronological view", async () => {
    localStorage.setItem("aw_suggestion_pref", "timeline");
    const today = luxon.DateTime.now().startOf("day").plus({ hours: 10 });

    onRpc("http://localhost:5600/api/0/buckets/*", () => [
        { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
        { type: "afkstatus", id: "afk", client: "aw-watcher-afk" },
    ]);

    pyEnv["aw.rule"].create([
        {
            name: "Discord Channel",
            regex: "#(.*?)\\s*\\|\\s*(.*?)\\s*-\\s*Discord",
            type: "messaging",
            template: "Discussing in channel: #$1 ($2)",
            always_active: false,
        },
        {
            name: "Discord Channel (web app)",
            regex: "(?:\\(\\d+\\)\\s)?Discord\\s\\|\\s#(.*?)\\s\\|\\s(.*?)\\|https:\\/\\/discord\\.com\\/channels\\/.*",
            type: "messaging",
            template: "Discussing in channel: #$1 ($2)",
            always_active: false,
        },
    ]);

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "Project 1" },
        },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", (request) => {
        if (request.url.includes("afk")) {
            return [
                {
                    timestamp: today.plus({ minutes: 10 }).toISO(),
                    duration: 600,
                    data: { status: "afk" },
                },
            ].reverse();
        } else {
            return [
                {
                    timestamp: today.toISO(),
                    duration: 600,
                    data: { title: "Coding A", url: "https://some-url.com" },
                },
                {
                    timestamp: today.plus({ minutes: 20 }).toISO(),
                    duration: 600,
                    data: { title: "Coding B", url: "https://some-url.com" },
                },
                {
                    timestamp: today.plus({ minutes: 30 }).toISO(),
                    duration: 600,
                    data: { title: "Coding A", url: "https://some-url.com" },
                },
            ].reverse();
        }
    });

    await openAssistant();

    const checkSuggestions = (elements) => {
        expect(".o_suggestions_suggestion").toHaveCount(elements.length);
        for (let i = 0; i < elements.length; i++) {
            expect(`.o_suggestions_suggestion_description:eq(${i})`).toHaveText(elements[i][0]);
            expect(`.o_suggestions_suggestion:eq(${i}) time`).toHaveText(elements[i][1]);
        }
    };

    checkSuggestions([
        ["Coding A", "0h 10m"],
        ["Away", "0h 10m"],
        ["Coding B", "0h 10m"],
        ["Coding A", "0h 10m"],
    ]);

    // Select the first row and verify it clears when switching views
    await contains(".o_suggestions_suggestion:eq(0)").click();
    expect(".o_suggestions_suggestion.o_isSelected").toHaveCount(1);
    await contains("button:contains('By Project')").click();
    expect(".o_suggestions_suggestion.o_isSelected").toHaveCount(0);

    // In project view, it should sum up non-afk identical titles:
    checkSuggestions([
        ["Coding A", "0h 20m"],
        ["Coding B", "0h 10m"],
    ]);

    // Switch back to timeline view and Consume the SECOND "Coding A"
    await contains("button:contains('Chronological')").click();
    await contains(`.o_suggestions_suggestion:eq(3) .o_aw_btn_remove`, { visible: false }).click();

    expect(".o_suggestions_suggestion").toHaveCount(3);

    const consumedEvents = JSON.parse(localStorage.getItem("aw_taken_deleted_events"));
    expect(consumedEvents).toEqual({
        '{"title":"Coding A","day":"2019-03-11"}': {
            duration: 600,
            isConsumed: false,
            timelineStartTimes: ["2019-03-11T10:30:00.000+01:00"],
            timelineDuration: 600,
        },
    });

    // Reload and assert the second "Coding A" is not present
    await reload();
    checkSuggestions([
        ["Coding A", "0h 10m"],
        ["Away", "0h 10m"],
        ["Coding B", "0h 10m"],
    ]);

    // Switch to project view and assert "Coding A" duration is 10m (not 20m)
    await contains("button:contains('By Project')").click();
    checkSuggestions([
        ["Coding A", "0h 10m"],
        ["Coding B", "0h 10m"],
    ]);

    // Remove Coding B in Project View
    await contains(`.o_suggestions_suggestion:eq(1) .o_aw_btn_remove`, { visible: false }).click();
    checkSuggestions([["Coding A", "0h 10m"]]);

    // Switch to timeline view and assert "Coding B" is gone
    await contains("button:contains('Chronological')").click();
    checkSuggestions([
        ["Coding A", "0h 10m"],
        ["Away", "0h 10m"],
    ]);
});

test("Timesheet Assistant - keeps manual project selection when selecting another suggestion", async () => {
    await openAssistant();
    const now = new Date();
    localStorage.clear();

    const events = [
        {
            timestamp: new Date(now - 1200 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://random.com",
                title: "Random Web Activity",
            },
        },
        {
            timestamp: new Date(now - 600 * 1000).toISOString(),
            duration: 120,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg1",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner B (partnerB@example.com)",
                subject: "Webocalypse Now stuff",
            },
        },
    ];

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_gmail_partners", () => ({
        "partnerB@example.com": {
            partner_name: "Partner B",
            project_id: 2, // Resolves to Webocalypse Now
        },
    }));

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "P1" },
            2: { project_id: 2, project_name: "Webocalypse Now" },
        },
    }));

    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [...events].reverse());

    await reload();

    expect(".o_suggestions_suggestion_description:contains('Random Web Activity')").toHaveCount(1);
    expect(".o_suggestions_suggestion_description:contains('Webocalypse Now stuff')").toHaveCount(
        1
    );

    await contains(".o_suggestions_suggestion:contains('Random Web Activity')").click();

    await selectFieldDropdownItem("project_id", "P1");

    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "P1 should be selected manually on the form",
    });

    await contains(".o_suggestions_suggestion:contains('Webocalypse Now stuff')").click();
    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "P1 should remain selected after clicking a suggestion mapped to Webocalypse Now",
    });
});

test("Timesheet Assistant: Discord rule matches both the desktop app and the browser window title", async () => {
    const today = luxon.DateTime.now().startOf("day");

    pyEnv["aw.rule"].create([
        {
            name: "Discord Channel",
            regex: "#(.*?)\\s*\\|\\s*(.*?)\\s*-\\s*Discord",
            type: "messaging",
            template: "Discussing in channel: #$1 ($2)",
            always_active: false,
        },
        {
            name: "Discord Channel (web app)",
            regex: "(?:\\(\\d+\\)\\s)?Discord\\s\\|\\s#(.*?)\\s\\|\\s(.*?)\\|https:\\/\\/discord\\.com\\/channels\\/.*",
            type: "messaging",
            template: "Discussing in channel: #$1 ($2)",
            always_active: false,
        },
    ]);

    onRpc("http://localhost:5600/api/0/buckets/", () => ({
        window: { type: "currentwindow", id: "window", client: "aw-watcher-window" },
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    // Desktop app: ActivityWatch reports the OS window title directly.
    onRpc("http://localhost:5600/api/0/buckets/window/events", () => [
        {
            timestamp: today.plus({ hours: 9 }).toISO(),
            duration: 1800,
            data: { title: "#timesheets-assistant | Odoo - Discord" },
        },
    ]);

    // Browser: ActivityWatch reports the tab title and url separately; they get
    // concatenated with "|" by extractWatcherActivity before being matched.
    onRpc("http://localhost:5600/api/0/buckets/web/events", () => [
        {
            timestamp: today.plus({ hours: 9, minutes: 30 }).toISO(),
            duration: 1800,
            data: {
                title: "Discord | #general | TeamChat",
                url: "https://discord.com/channels/1111/2222",
            },
        },
    ]);

    await openAssistant();

    expect(".o_suggestions_suggestion").toHaveCount(2);
    expect(".o_suggestions_suggestion_description:eq(0)").toHaveText(
        "Discussing in channel: #timesheets-assistant (Odoo)"
    );
    expect(".o_suggestions_suggestion_description:eq(1)").toHaveText(
        "Discussing in channel: #general (TeamChat)"
    );

    await contains(".o_suggestions_suggestion:eq(0)").click();

    expect(".o_activitywatch_sync_timesheet_creation_form .field-description textarea").toHaveValue(
        "Discussing in channel: #timesheets-assistant (Odoo)"
    );
});

test("Timesheet Assistant: reset selected suggestion before selecting another", async () => {
    const now = new Date();
    localStorage.clear();
    const events = [
        {
            timestamp: new Date(now - 12600 * 1000).toISOString(),
            duration: 80,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg1",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner A (partnerA@example.com)",
                subject: "P1 stuff",
            },
        },
        {
            timestamp: new Date(now - 11400 * 1000).toISOString(),
            duration: 29 * 60 + 15,
            data: {
                url: "https://mail.google.com/mail/u/0/#inbox/msg2",
                title: "Gmail - Reading",
                gmail_activity: "reading_email",
                from: "Partner B (partnerB@example.com)",
                subject: "Webocalypse Now stuff",
            },
        },
    ];

    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));

    onRpc("account.analytic.line", "resolve_gmail_partners", () => ({
        "partnerA@example.com": {
            partner_name: "Partner A",
            project_id: 1, // Resolves to P1
        },
        "partnerB@example.com": {
            partner_name: "Partner B",
            project_id: 2, // Resolves to Webocalypse Now
        },
    }));

    onRpc("account.analytic.line", "resolve_assistant_models_targets", () => ({
        "project.project": {
            1: { project_id: 1, project_name: "P1" },
            2: { project_id: 2, project_name: "Webocalypse Now" },
        },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => [...events].reverse());

    await openAssistant();

    await contains(".o_suggestions_suggestion:contains('P1 stuff')").click();
    expect("div[name='project_id'] input").toHaveValue("P1", {
        message: "P1 should be selected on the form",
    });
    // unselect the P1 suggestion
    await contains(".o_suggestions_suggestion:contains('P1 stuff')").click();
    await contains(".o_suggestions_suggestion:contains('Webocalypse Now stuff')").click();
    expect("div[name='project_id'] input").toHaveValue("Webocalypse Now", {
        message: "Webocalypse Now should be selected after selecting a different suggestion",
    });
});

test("Timesheet Assistant merge method correctly clips events and recalculates duration", () => {
    const merge = TimesheetAssistantModel.prototype.merge;

    const startOfDay = luxon.DateTime.fromISO("2026-08-12T00:00:00");
    const ranges = [
        {
            name: "Meeting 1",
            start: startOfDay.plus({ hours: 10 }), // 10:00 to 12:00
            stop: startOfDay.plus({ hours: 12 }),
            duration: 7200,
        },
        {
            name: "Meeting 2",
            start: startOfDay.plus({ hours: 15 }), // 15:00 to 16:00
            stop: startOfDay.plus({ hours: 16 }),
            duration: 3600,
        },
    ];

    const intervalsToInclude = [
        {
            name: "Fully Overlapped",
            start: startOfDay.plus({ hours: 10, minutes: 30 }), // 10:30 to 11:00
            stop: startOfDay.plus({ hours: 11 }),
            duration: 1800,
        },
        {
            name: "Partially Overlapped",
            start: startOfDay.plus({ hours: 14, minutes: 30 }), // 14:30 to 15:30
            stop: startOfDay.plus({ hours: 15, minutes: 30 }),
            duration: 3600,
        },
        {
            name: "Zero-Duration",
            start: startOfDay.plus({ hours: 15 }), // 15:00 to 15:00 (Squished)
            stop: startOfDay.plus({ hours: 15 }),
            duration: 103,
        },
    ];

    merge(ranges, intervalsToInclude);

    // should have dropped the fully overlapped event and the zero duration event.
    // should only contain Meeting 1, the Clipped Event, and Meeting 2.
    expect(ranges.length).toBe(3);

    expect(ranges[0].name).toBe("Meeting 1");

    expect(ranges[1].name).toBe("Partially Overlapped");
    expect(ranges[1].start.toISO()).toBe(startOfDay.plus({ hours: 14, minutes: 30 }).toISO());
    expect(ranges[1].stop.toISO()).toBe(startOfDay.plus({ hours: 15 }).toISO());
    expect(ranges[1].duration).toBe(1800);

    expect(ranges[2].name).toBe("Meeting 2");
});

test("Timesheet Assistant: fetchData/load commit their data in a single reactive update, not one render per intermediate mutation", async () => {
    // TimesheetAssistantModel.fetchData() builds up a plain, non-reactive `data` object
    // throughout its (multi-`await`) pipeline and only assigns `this.data = data` once, right
    // at the end. If a future change went back to mutating `this.data.grouped`/`recordsByStart`/
    // `totalDuration`/etc. directly and incrementally instead, TimesheetsAssistant would
    // re-render once per such mutation instead of once per fetchData()/load() call — this test
    // pins that invariant down by counting actual onPatched calls, not just asserting on the
    // final rendered output (which would look identical either way).
    let model;
    let patchCount = 0;
    patchWithCleanup(TimesheetsAssistant.prototype, {
        setup() {
            super.setup();
            model = this.model;
            onPatched(() => patchCount++);
        },
    });

    // Mock the two boundaries fetchData() awaits on, so its pipeline actually spans multiple
    // microtask ticks (like it does for real) instead of resolving synchronously.
    onRpc("http://localhost:5600/api/0/buckets/*", () => ({
        web: { type: "web.tab.current", id: "web", client: "aw-watcher-web" },
    }));
    onRpc("http://localhost:5600/api/0/buckets/*/events*", () => []);

    await openAssistant();

    // Calling fetchData()/load() directly (rather than via date-navigation, which legitimately
    // triggers its own separate render by mutating model.data.currentDate first) isolates
    // exactly the behavior under test.
    patchCount = 0;
    await model.fetchData();
    await animationFrame();
    expect(patchCount).toBe(1);

    patchCount = 0;
    await model.load();
    await animationFrame();
    expect(patchCount).toBe(1);
});

test("Timesheet Assistant: updates timesheet when date is changed", async () => {
    await openAssistant();
    onRpc("get_formview_id", () => false);
    const timesheetId = pyEnv["account.analytic.line"].create({
        user_id: serverState.userId,
        name: "Test 1",
        date: "2019-03-11",
        project_id: 1,
        task_id: 1,
        unit_amount: 1,
        company_id: user.activeCompany.id,
    });

    await reload();


    expect("div[name='timesheets_section'] > div > a").toHaveCount(1);
    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
1h 00m
over
7h 36m`
    );

    await contains("div[name='timesheets_section'] > div > a").click();

    const formSelector =
        "div[name='timesheets_section'] > div > .o_activitywatch_sync_timesheet_edition_form";

    expect(formSelector).toHaveCount(1);

    await contains(`${formSelector} div[name='task_field'] .o_external_button`, {
        visible: false,
    }).click();
    expect(".o_dialog").toHaveCount(1);

    pyEnv["account.analytic.line"].write([timesheetId], {
        date: "2019-03-12",
    });
    await contains(".o_dialog .o_form_button_save").click();
    expect(".o_dialog").toHaveCount(0);

    expect("div[name='timesheets_section'] > div > a").toHaveCount(0, {
        message: "The timesheet should disappear after its date changes",
    });

    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
0h 00m
over
7h 36m`
    );

    await contains(".o_calendar_button_next").click();
    expect("div[name='timesheets_section'] > div > a").toHaveCount(1, {
        message: "The timesheet should appear on its new date",
    });

    expect(".o_activity_watch_timesheet_right_tots").toHaveText(
        `Total
1h 00m
over
7h 36m`
    );
});
