import { beforeEach, describe, dblclick, expect, test } from "@odoo/hoot";
import {
    click,
    drag,
    hover,
    keyDown,
    keyUp,
    pointerDown,
    press,
    queryAllTexts,
    queryOne,
    queryRect,
    scroll,
    waitFor,
    waitForNone,
} from "@odoo/hoot-dom";
import { advanceFrame, advanceTime, animationFrame, mockDate, runAllTimers } from "@odoo/hoot-mock";
import {
    contains,
    defineParams,
    editSelectMenu,
    fields,
    mockService,
    onRpc,
    patchWithCleanup,
    toggleMenuItem,
    toggleSearchBarMenu,
    validateSearch,
} from "@web/../tests/web_test_helpers";
import { ResUsers, Tasks, defineGanttModels } from "./gantt_mock_models";
import {
    CLASSES,
    SELECTORS,
    clickCell,
    cssClassPresencePerCellInColumn,
    dragPill,
    editPill,
    focusToday,
    ganttControlsChanges,
    getCell,
    getGridContent,
    getPill,
    getPillWrapper,
    hoverGridCell,
    hoverPillCell,
    mountGanttView,
    resizePill,
    selectCustomRange,
    selectRange,
} from "./web_gantt_test_helpers";

import { omit, pick } from "@web/core/utils/objects";

// Hard-coded daylight saving dates from 2019
const DST_DATES = {
    winterToSummer: {
        before: "2019-03-30",
        after: "2019-03-31",
    },
    summerToWinter: {
        before: "2019-10-26",
        after: "2019-10-27",
    },
};

describe.current.tags("desktop");

defineGanttModels();
beforeEach(() => {
    mockDate("2018-12-20T08:00:00", +1);
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
});

test("date navigation with timezone (1h)", async () => {
    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step(kwargs.domain.toString());
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
    });

    expect.verifySteps(["&,start,<,2019-02-28 23:00:00,stop,>,2018-11-30 23:00:00"]);

    expect(getGridContent().range).toBe("12/01/2018 -> 02/28/2019");

    // switch to day view and check day navigation
    await selectRange("Day");
    await ganttControlsChanges();

    expect.verifySteps(["&,start,<,2018-12-21 23:00:00,stop,>,2018-12-18 23:00:00"]);
    expect(getGridContent().range).toBe("Day");

    // switch to week view and check week navigation
    await selectRange("Week");
    await ganttControlsChanges();

    expect.verifySteps(["&,start,<,2018-12-29 23:00:00,stop,>,2018-12-08 23:00:00"]);
    expect(getGridContent().range).toBe("Week");

    // switch to month view and check week navigation
    await selectRange("Month");
    await ganttControlsChanges();

    expect.verifySteps(["&,start,<,2019-01-31 23:00:00,stop,>,2018-10-31 23:00:00"]);
    expect(getGridContent().range).toBe("Month");

    // switch to quarter view and check week navigation
    await selectRange("Quarter");
    await ganttControlsChanges();

    expect.verifySteps(["&,start,<,2019-03-31 23:00:00,stop,>,2018-06-30 23:00:00"]);
    expect(getGridContent().range).toBe("Quarter");

    // switch to year view and check year navigation
    await selectRange("Year");
    await ganttControlsChanges();

    expect.verifySteps(["&,start,<,2019-12-31 23:00:00,stop,>,2016-12-31 23:00:00"]);
    expect(getGridContent().range).toBe("Year");
});

test("if a on_create is specified, execute the action rather than opening a dialog. And reloads after the action", async () => {
    mockService("action", {
        doAction(action, options) {
            expect.step(`[action] ${action}`);
            expect(options.additionalContext).toEqual({
                default_start: "2018-11-30 23:00:00",
                default_stop: "2018-12-31 23:00:00",
                lang: "en",
                allowed_company_ids: [1],
                start: "2018-11-30 23:00:00",
                stop: "2018-12-31 23:00:00",
                tz: "taht",
                uid: 7,
            });
            options.onClose();
        },
    });

    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" on_create="this_is_create_action" />',
    });

    expect.verifySteps(["get_gantt_data"]);

    await contains(SELECTORS.addButton + ":visible").click();
    expect.verifySteps(["[action] this_is_create_action", "get_gantt_data"]);
});

test("select cells to create a task", async () => {
    mockService("dialog", {
        add(_, props) {
            expect.step(`[dialog] ${props.title}`);
            expect(props.context).toEqual({
                default_start: "2018-12-19 11:00:00",
                default_stop: "2018-12-21 23:00:00",
                lang: "en",
                allowed_company_ids: [1],
                start: "2018-12-19 11:00:00",
                stop: "2018-12-21 23:00:00",
                tz: "taht",
                uid: 7,
            });
        },
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    const { drop, moveTo } = await contains(getCell("19", "December 2018")).drag();
    await moveTo(getCell("21", "December 2018"), { position: { x: 30 }, relative: true });
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveText("12/19/2018, 12:00 PM");
    expect(SELECTORS.stopBadge).toHaveText("12/22/2018, 12:00 AM");
    await drop();

    expect.verifySteps(["[dialog] Create"]);
});

test("can cancel selection", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    const { cancel, moveTo } = await contains(getCell("19", "December 2018")).drag();
    await moveTo(getCell("21", "December 2018"), { position: { x: 30 }, relative: true });
    await animationFrame();

    expect(".o_cell_ghost").toHaveCount();

    await cancel();
    await animationFrame();

    expect(".o_cell_ghost").not.toHaveCount();
});

test("drag and drop on the same cell to create a task", async () => {
    mockService("dialog", {
        add(_, props) {
            expect.step(`[dialog] ${props.title}`);
            expect(props.context).toEqual({
                default_start: "2018-12-15 11:00:00",
                default_stop: "2018-12-15 23:00:00",
                lang: "en",
                allowed_company_ids: [1],
                start: "2018-12-15 11:00:00",
                stop: "2018-12-15 23:00:00",
                tz: "taht",
                uid: 7,
            });
        },
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    const { drop, moveTo } = await contains(getCell("15", "December 2018")).drag();
    await moveTo(getCell("15", "December 2018"));
    expect(SELECTORS.startBadge).toHaveText("12/15/2018, 12:00 PM");
    expect(SELECTORS.stopBadge).toHaveText("12/16/2018, 12:00 AM");
    await drop();

    expect.verifySteps(["[dialog] Create"]);
});

test("row id is properly escaped to avoid name issues in selection", async () => {
    mockService("dialog", {
        add() {
            expect.step("[dialog]");
        },
    });

    ResUsers._records[0].name = "O'Reilly";

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>',
    });

    await hoverGridCell("11", "December 2018");
    await clickCell("11", "December 2018");

    expect.verifySteps(["[dialog]"]);
});

test("select cells to plan a task: 1-level grouped", async () => {
    mockService("dialog", {
        add(_, props) {
            expect.step(`[dialog] ${props.title}`);
            expect(props.context).toEqual({
                default_start: "2018-12-11 11:00:00",
                default_stop: "2018-12-12 23:00:00",
                default_user_id: 1,
                lang: "en",
                search_default_user_id: 1,
                allowed_company_ids: [1],
                start: "2018-12-11 11:00:00",
                stop: "2018-12-12 23:00:00",
                tz: "taht",
                uid: 7,
                user_id: 1,
            });
        },
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["user_id"],
    });

    await hoverGridCell("11", "December 2018", "User 1");
    const { moveTo, drop } = await contains(getCell("11", "December 2018", "User 1")).drag();
    moveTo(getCell("12", "December 2018", "User 1"));
    await runAllTimers(); // Pointer move is subjected to throttleForAnimation in gantt
    await drop();

    expect.verifySteps(["[dialog] Create"]);
});

test("select cells to plan a task: 2-level grouped", async () => {
    mockService("dialog", {
        add(_, props) {
            expect.step(`[dialog] ${props.title}`);
            expect(props.context).toEqual({
                default_project_id: 1,
                default_start: "2018-12-11 11:00:00",
                default_stop: "2018-12-12 23:00:00",
                default_user_id: 1,
                allowed_company_ids: [1],
                lang: "en",
                project_id: 1,
                search_default_project_id: 1,
                search_default_user_id: 1,
                start: "2018-12-11 11:00:00",
                stop: "2018-12-12 23:00:00",
                tz: "taht",
                uid: 7,
                user_id: 1,
            });
        },
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["user_id", "project_id"],
    });
    await hoverGridCell("11", "December 2018");
    const dragAndDrop1 = await contains(getCell("11", "December 2018")).drag();
    dragAndDrop1.moveTo(getCell("12", "December 2018"));
    await advanceTime(20); // Pointer move is subjected to throttleForAnimation in gantt
    dragAndDrop1.drop();
    // nothing happens
    await hoverGridCell("11", "December 2018", "Project 1");
    await advanceTime(20);
    const dragAndDrop2 = await contains(getCell("11", "December 2018", "Project 1")).drag();
    dragAndDrop2.moveTo(getCell("12", "December 2018", "Project 1"));
    await advanceTime(20);
    await dragAndDrop2.drop();

    expect.verifySteps(["[dialog] Create"]);
});

test("hovering a cell with special character", async () => {
    expect.assertions(1);

    // add special character to data
    ResUsers._records[0].name = "User' 1";

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["user_id", "project_id"],
    });

    // hover on first header "User' 1" with data-row-id equal to [{"user_id":[1,"User' 1"]}]
    // the "'" must be escaped with "\\'" in findSiblings to prevent the selector to crash
    await contains(".o_gantt_row_header").hover();

    expect(".o_gantt_row_header:first").toHaveClass("o_gantt_group_hovered", {
        message: "hover style is applied to the element",
    });
});

test("open a dialog to add a new task", async () => {
    defineParams({
        lang_parameters: {
            time_format: "%H:%M:%S",
        },
    });

    Tasks._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="start"/>
                <field name="stop"/>
            </form>
        `,
    };

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
    });

    expect(".modal").toHaveCount(0);

    await contains(SELECTORS.addButton + ":visible").click();

    // check that the dialog is opened with prefilled fields
    expect(".modal").toHaveCount(1);
    expect(".o_field_widget[name=start] button").toHaveValue("12/01/2018 00:00:00");
    expect(".o_field_widget[name=stop] button").toHaveValue("01/01/2019 00:00:00");
});

test("open a dialog to create/edit a task", async () => {
    defineParams({
        lang_parameters: {
            time_format: "%H:%M:%S",
        },
    });

    Tasks._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="start"/>
                <field name="stop"/>
                <field name="stage"/>
                <field name="project_id"/>
                <field name="user_id"/>
            </form>
        `,
    };

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" plan="false"/>',
        groupBy: ["user_id", "project_id", "stage"],
    });

    // open dialog to create a task
    expect(".modal").toHaveCount(0);
    await hoverGridCell("10", "December 2018", "In Progress");
    await clickCell("10", "December 2018", "In Progress");

    // check that the dialog is opened with prefilled fields
    expect(".modal").toHaveCount(1);
    expect(".modal-title").toHaveText("Create");
    await contains(".o_field_widget[name=name] input").edit("Task 8");
    expect(".o_field_widget[name=start] button").toHaveValue("12/10/2018 00:00:00");
    expect(".o_field_widget[name=stop] button").toHaveValue("12/11/2018 00:00:00");
    expect(".o_field_widget[name=project_id] input").toHaveValue("Project 1");
    expect(".o_field_widget[name=user_id] input").toHaveValue("User 1");
    expect(".o_field_widget[name=stage] input").toHaveValue("In Progress");

    // create the task
    await contains(".o_form_button_save").click();
    expect(".modal").toHaveCount(0);

    // open dialog to view a task
    await editPill("Task 8");
    expect(".modal").toHaveCount(1);
    expect(".modal-title").toHaveText("Open");
    expect(".o_field_widget[name=name] input").toHaveValue("Task 8");
    expect(".o_field_widget[name=start] button").toHaveValue("12/10/2018 00:00:00");
    expect(".o_field_widget[name=stop] button").toHaveValue("12/11/2018 00:00:00");
    expect(".o_field_widget[name=project_id] input").toHaveValue("Project 1");
    expect(".o_field_widget[name=user_id] input").toHaveValue("User 1");
    expect(".o_field_widget[name=stage] input").toHaveValue("In Progress");
});

test("open a dialog to create a task when grouped by many2many field", async () => {
    Tasks._fields.user_ids = fields.Many2many({
        string: "Assignees",
        relation: "res.users",
    });
    Tasks._records[0].user_ids = [1, 2];
    Tasks._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="start"/>
                <field name="stop"/>
                <field name="project_id"/>
                <field name="user_ids" widget="many2many_tags"/>
            </form>
        `,
    };

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" plan="false"/>`,
        groupBy: ["user_ids", "project_id"],
    });

    // Check grouped rows
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assignees",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    title: "Task 2",
                },
                {
                    level: 1,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    title: "Task 4",
                },
                {
                    level: 0,
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    title: "Task 3",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    title: "Task 7",
                },
            ],
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [{ title: "1", colSpan: "Out of bounds (1)  -> 31 December 2018" }],
        },
        {
            title: "Project 1",
            pills: [
                { level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018", title: "Task 1" },
            ],
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "Out of bounds (1)  -> 31 December 2018" }],
        },
        {
            title: "Project 1",
            pills: [
                { level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018", title: "Task 1" },
            ],
        },
    ]);

    // open dialog to create a task with two many2many values
    await hoverGridCell("10", "December 2018", "Project 1", { num: 2 });
    await clickCell("10", "December 2018", "Project 1", { num: 2 });
    await contains(".o_field_widget[name=name] input").edit("NEW TASK 0");
    await contains(".o_field_widget[name=user_ids] input").fill("User 2", { confirm: false });
    await runAllTimers();
    await contains(".o-autocomplete--dropdown-menu li:first-child a").click();
    await contains(".o_form_button_save").click();
    expect(".modal").toHaveCount(0);
    const [, , , , , sixthRow, , eighthRow] = getGridContent().rows;
    expect(sixthRow).toEqual({
        title: "Project 1",
        pills: [
            { level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018", title: "Task 1" },
            { level: 1, colSpan: "10 December 2018 -> 10 December 2018", title: "NEW TASK 0" },
        ],
    });
    expect(eighthRow).toEqual({
        title: "Project 1",
        pills: [
            { level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018", title: "Task 1" },
            { level: 1, colSpan: "10 December 2018 -> 10 December 2018", title: "NEW TASK 0" },
        ],
    });

    // open dialog to create a task with no many2many values
    await hoverGridCell("24", "December 2018", "Project 2");
    await clickCell("24", "December 2018", "Project 2");
    await contains(".o_field_widget[name=name] input").edit("NEW TASK 1");
    await contains(".o_form_button_save").click();
    expect(".modal").toHaveCount(0);
    const [, , , fourthRow] = getGridContent().rows;
    expect(fourthRow).toEqual({
        title: "Project 2",
        pills: [
            {
                level: 0,
                colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                title: "Task 7",
            },
            { level: 0, colSpan: "24 December 2018 -> 24 December 2018", title: "NEW TASK 1" },
        ],
    });
});

test("open a dialog to create a task, does not have a delete button", async () => {
    Tasks._views = {
        form: `<form><field name="name"/></form>`,
    };
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" plan="false"/>',
        groupBy: [],
    });
    await hoverGridCell("10", "December 2018");
    await clickCell("10", "December 2018");
    expect(".modal").toHaveCount(1);
    expect(".modal .o_btn_remove").toHaveCount(0);
});

test("open a dialog to edit a task, has a delete buttton", async () => {
    Tasks._views = {
        form: `<form><field name="name"/></form>`,
    };
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: [],
    });
    await editPill("Task 1");
    expect(".modal").toHaveCount(1);
    expect(".modal .o_form_button_remove").toHaveCount(1);
});

test("clicking on delete button in edit dialog triggers a confirmation dialog, clicking discard does not call unlink on the model", async () => {
    Tasks._views = {
        form: `<form><field name="name"/></form>`,
    };
    onRpc(({ method }) => {
        if (method === "web_unlink") {
            expect.step(method);
        }
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: [],
    });
    expect(".o_dialog").toHaveCount(0);
    await editPill("Task 1");
    expect(".o_dialog").toHaveCount(1);
    // trigger the delete button
    await contains(".o_dialog .o_form_button_remove").click();
    expect(".o_dialog").toHaveCount(2);

    const button = queryOne(".o_dialog:not(.o_inactive_modal) footer .btn-secondary");
    expect(button).toHaveText("No, keep it");
    await contains(button).click();
    expect(".o_dialog").toHaveCount(1);
    expect.verifySteps([]);
});

test("clicking on delete button in edit dialog triggers a confirmation dialog, clicking ok calls unlink on the model", async () => {
    Tasks._views = {
        form: `<form><field name="name"/></form>`,
    };
    onRpc("web_unlink", () => {
        expect.step("web_unlink");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: [],
    });
    expect(".o_dialog").toHaveCount(0);
    await editPill("Task 1");
    expect(".o_dialog").toHaveCount(1);
    // trigger the delete button
    await contains(".o_dialog .o_form_button_remove").click();
    expect(".o_dialog").toHaveCount(2);
    const button = queryOne(".o_dialog:not(.o_inactive_modal) footer .btn-danger");
    expect(button).toHaveText("Delete");
    await contains(button).click();
    expect(".o_dialog").toHaveCount(0);
    expect.verifySteps(["web_unlink"]);
    // Check that the pill has disappeared
    await expect(editPill("Task 1")).rejects.toThrow();
});

test("create dialog with timezone", async () => {
    defineParams({
        lang_parameters: {
            time_format: "%H:%M:%S",
        },
    });

    expect.assertions(3);

    Tasks._views = {
        form: `<form><field name="start"/><field name="stop"/></form>`,
    };

    onRpc(({ method, args }) => {
        if (method === "web_save") {
            expect(args[1]).toEqual({
                start: "2018-12-09 23:00:00",
                stop: "2018-12-10 23:00:00",
            });
        }
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" plan="false"/>',
    });

    await hoverGridCell("10", "December 2018");
    await clickCell("10", "December 2018");
    expect(".o_field_widget[name=start] button").toHaveValue("12/10/2018 00:00:00");
    expect(".o_field_widget[name=stop] button").toHaveValue("12/11/2018 00:00:00");
    await contains(".o_form_button_save").click();
});

test("open a dialog to plan a task", async () => {
    Tasks._views = {
        list: '<list><field name="name"/></list>',
        search: '<search><field name="name"/></search>',
    };
    Tasks._records.push(
        { id: 41, name: "Task 41" },
        { id: 42, name: "Task 42", stop: "2018-12-31 18:29:59" },
        { id: 43, name: "Task 43", start: "2018-11-30 18:30:00" }
    );
    onRpc(({ method, args, model }) => {
        if (method === "write") {
            expect.step(model);
            expect(args[0]).toEqual([41, 42], { message: "should write on the selected ids" });
            expect(args[1]).toEqual({
                start: "2018-12-09 23:00:00",
                stop: "2018-12-10 23:00:00",
            });
        }
    });
    onRpc("has_group", () => true);
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
    });

    // click on the plan button
    await hoverGridCell("10", "December 2018");
    await clickCell("10", "December 2018");
    expect(".modal .o_list_view").toHaveCount(1);
    expect(queryAllTexts(".modal .o_list_view .o_data_cell")).toEqual([
        "Task 41",
        "Task 42",
        "Task 43",
    ]);

    // Select the first two tasks
    await contains(".modal .o_list_view tbody tr:nth-child(1) input").click();
    await contains(".modal .o_list_view tbody tr:nth-child(2) input").click();
    await contains(".modal footer .o_select_button").click();
    expect.verifySteps(["tasks"]);
});

test("open a dialog to plan a task (multi-level)", async () => {
    Tasks._views = {
        list: '<list><field name="name"/></list>',
        search: '<search><field name="name"/></search>',
    };
    Tasks._records.push({ id: 41, name: "Task 41" });

    onRpc(({ args, method, model }) => {
        if (method === "write") {
            expect.step(model);
            expect(args[0]).toEqual([41], { message: "should write on the selected id" });
            expect(args[1]).toEqual(
                {
                    project_id: 1,
                    stage: "todo",
                    start: "2018-12-09 23:00:00",
                    stop: "2018-12-10 23:00:00",
                    user_id: 1,
                },
                { message: "should write on all the correct fields" }
            );
        }
    });
    onRpc("has_group", () => true);

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["user_id", "project_id", "stage"],
    });

    // click on the plan button
    await hoverGridCell("10", "December 2018", "To Do");
    await clickCell("10", "December 2018", "To Do");
    expect(".modal .o_list_view").toHaveCount(1);
    expect(".modal .o_list_view .o_data_cell").toHaveText("Task 41");

    // Select the first task
    await contains(".modal .o_list_view tbody tr:nth-child(1) input").click();
    await animationFrame();
    await contains(".modal-footer .o_select_button").click();
    expect.verifySteps(["tasks"]);
});

test("expand/collapse rows", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["user_id", "project_id", "stage"],
    });
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "In Progress" },
        { title: "To Do" },
        { title: "Project 2", isGroup: true },
        { title: "Done" },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);

    // collapse all groups
    await contains(SELECTORS.collapseButton).click();
    expect(SELECTORS.expandButton).toHaveCount(1);
    expect(SELECTORS.collapseButton).toHaveCount(0);
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "User 1", isGroup: true },
        { title: "User 2", isGroup: true },
    ]);

    // expand all groups
    await contains(SELECTORS.expandButton).click();
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "In Progress" },
        { title: "To Do" },
        { title: "Project 2", isGroup: true },
        { title: "Done" },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);

    // collapse the first real group ("User 1"; the "Undefined Assign To" group is 1st/2nd/3rd child)
    await contains(`${SELECTORS.rowHeader}${SELECTORS.group}:nth-child(4)`).click();
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);
    expect(SELECTORS.expandButton).toHaveCount(1);
    expect(SELECTORS.collapseButton).toHaveCount(0);

    // expand the first real group
    await contains(`${SELECTORS.rowHeader}${SELECTORS.group}:nth-child(4)`).click();
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "In Progress" },
        { title: "To Do" },
        { title: "Project 2", isGroup: true },
        { title: "Done" },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
});

test("collapsed rows remain collapsed at reload", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["user_id", "project_id", "stage"],
    });
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "In Progress" },
        { title: "To Do" },
        { title: "Project 2", isGroup: true },
        { title: "Done" },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);

    // collapse the first real group ("User 1"; the "Undefined Assign To" group is 1st/2nd/3rd child)
    await contains(`${SELECTORS.rowHeader}${SELECTORS.group}:nth-child(4)`).click();
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);

    // reload
    await validateSearch();
    expect(getGridContent().rows.map((r) => omit(r, "pills"))).toEqual([
        { title: "Undefined Assign To", isGroup: true },
        { title: "Undefined Project", isGroup: true },
        { title: "Undefined Stage" },
        { title: "User 1", isGroup: true },
        { title: "User 2", isGroup: true },
        { title: "Project 1", isGroup: true },
        { title: "Cancelled" },
        { title: "Done" },
        { title: "Project 2", isGroup: true },
        { title: "Cancelled" },
    ]);
});

test("resize a pill", async () => {
    onRpc("write", ({ args }) => {
        // initial dates -- start: '2018-11-30 18:30:00', stop: '2018-12-31 18:29:59'
        expect.step(args);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 1]],
        context: { initialDate: "2018-12-25" },
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    expect(SELECTORS.pill).toHaveCount(1, { message: "there should be one pill (Task 1)" });
    expect(SELECTORS.resizable).toHaveCount(1);
    expect(SELECTORS.resizeHandle).toHaveCount(0);

    await contains(getPillWrapper("Task 1")).hover();

    // No start resizer because the start date overflows
    expect(SELECTORS.resizeStartHandle).toHaveCount(0);
    expect(SELECTORS.resizeEndHandle).toHaveCount(1);

    // resize to one cell smaller at end (-1 day)
    let drop = await resizePill(getPillWrapper("Task 1"), "end", -1, false);
    await waitFor(SELECTORS.stopBadge + ":contains(12/30/2018, 7:29 PM (-24 hours))");
    expect(SELECTORS.stopBadge).toHaveClass("text-danger");
    expect(SELECTORS.startBadge).toHaveText("11/30/2018, 7:30 PM");
    await drop();

    await selectCustomRange({ startDate: "2018-11-10", stopDate: "2018-11-30" });

    expect(SELECTORS.pill).toHaveCount(1, { message: "there should still be one pill (Task 1)" });
    expect(SELECTORS.resizable).toHaveCount(1);

    await contains(getPillWrapper("Task 1")).hover();

    // No end resizer because the end date overflows
    expect(SELECTORS.resizeStartHandle).toHaveCount(1);
    expect(SELECTORS.resizeEndHandle).toHaveCount(0);

    // resize to one cell smaller at start (-1 day)
    drop = await resizePill(getPillWrapper("Task 1"), "start", -1, false);
    await waitFor(SELECTORS.startBadge + ":contains(11/29/2018, 7:30 PM (+24 hours))");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveText("12/30/2018, 7:29 PM");
    await drop();

    expect.verifySteps([
        [[1], { stop: "2018-12-30 18:29:59" }],
        [[1], { start: "2018-11-29 18:30:00" }],
    ]);
});

test("action undo: resize a pill", async () => {
    expect.assertions(8);

    onRpc("gantt_undo_drag_drop", function ({ model, args }) {
        expect(args[0]).toEqual(1);
        expect(args[1]).toEqual("reschedule");
        expect(args[2]).toEqual(
            {
                start: "2018-11-30 18:30:00",
                stop: "2018-12-31 18:29:59",
            },
            { message: "all modified fields should be correctly set back to their initial values" }
        );
        return this.env[model].write([args[0]], args[2]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 1]],
        context: { initialDate: "2018-12-25" },
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    const initialGridContent = [
        {
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
    ];
    expect(getGridContent().rows).toEqual(initialGridContent);

    await contains(getPillWrapper("Task 1")).hover();
    // resize to one cell smaller at end (-1 day)
    const drop = await resizePill(getPillWrapper("Task 1"), "end", -1, false);
    await drop();
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 30 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
    expect(".o_notification_content").toHaveText("Record rescheduled");

    // undo the rescheduling of the pill
    await contains(".o_notification_buttons button i[title='Undo']").click();
    expect(getGridContent().rows).toEqual(initialGridContent, {
        message: "the pill should be back to its initial state",
    });
    expect(".o_notification_content").toHaveText("Record reschedule undone");
});

test("resize pill in year mode", async () => {
    onRpc("write", ({ args }) => {
        expect.step(args);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_range="year" />',
    });
    // Make sure Task 5 is around the center of the screen to avoid side-scrolling
    await contains(".o_gantt_scroll_container").scroll({ left: 1550 });
    expect(getPillWrapper("Task 5")).toHaveClass(CLASSES.resizable);

    const drop = await resizePill(getPillWrapper("Task 5"), "end", { x: 200 }, false);
    expect(SELECTORS.startBadge).toHaveText("11/8/2018");
    expect(SELECTORS.stopBadge).toHaveText("1/4/2019 (+1 months)");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();
    expect.verifySteps([[[5], { stop: "2019-01-04 01:34:34" }]]);
});

test("resize a pill (2)", async () => {
    onRpc("write", ({ args }) => expect.step(args));

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 2]],
    });

    expect(SELECTORS.pill).toHaveCount(1);

    await contains(getPillWrapper("Task 2")).hover();

    expect(getPillWrapper("Task 2")).toHaveClass(CLASSES.resizable);
    expect(SELECTORS.resizeHandle).toHaveCount(2);

    // resize to one cell larger
    const drop = await resizePill(getPillWrapper("Task 2"), "end", +1, false);
    await waitFor(SELECTORS.stopBadge + ":contains(12/23/2018, 7:29 AM (+24 hours))");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    expect(SELECTORS.startBadge).toHaveText("12/17/2018, 12:30 PM");
    await drop();

    expect(".modal").toHaveCount(0);
    expect.verifySteps([[[2], { stop: "2018-12-23 06:29:59" }]]);
});

test("resize a pill: invalid result", async () => {
    Tasks._records[1].start = "2018-12-17 10:30:00";
    Tasks._records[1].stop = "2018-12-17 15:30:00";
    onRpc("write", () => {
        throw new Error("Pill should not be resized");
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 2]],
    });

    expect(SELECTORS.pill).toHaveCount(1);

    await contains(getPillWrapper("Task 2")).hover();

    expect(getPillWrapper("Task 2")).toHaveClass(CLASSES.resizable);
    expect(SELECTORS.resizeHandle).toHaveCount(2);
    expect(getGridContent().rows).toEqual([
        {
            pills: [{ title: "Task 2", level: 0, colSpan: "17 December 2018 -> 17 December 2018" }],
        },
    ]);

    // shift end date towards start date
    await resizePill(getPillWrapper("Task 2"), "end", -1);

    expect(".modal").toHaveCount(0);
    expect(getGridContent().rows).toEqual([
        {
            pills: [{ title: "Task 2", level: 0, colSpan: "17 December 2018 -> 17 December 2018" }],
        },
    ]);
    expect(".o_notification").toHaveCount(1);
    expect(".o_notification .o_notification_body").toHaveText(
        "Ending date cannot be before the starting date"
    );
    await contains(".o_notification_close").click();

    // shift start date towards end date
    await resizePill(getPillWrapper("Task 2"), "start", +1);

    expect(".modal").toHaveCount(0);
    expect(getGridContent().rows).toEqual([
        {
            pills: [{ title: "Task 2", level: 0, colSpan: "17 December 2018 -> 17 December 2018" }],
        },
    ]);
    expect(".o_notification").toHaveCount(1);
    expect(".o_notification .o_notification_body").toHaveText(
        "Starting date cannot be after the ending date"
    );
});

test.tags("desktop");
test("resize a pill: quickly enter the neighbour pill when resize start", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "in", [4, 7]]],
    });
    expect(SELECTORS.pill).toHaveCount(2);
    await contains(getPillWrapper("Task 7")).hover();
    expect(getPillWrapper("Task 7")).toHaveClass(CLASSES.resizable);
    expect(SELECTORS.resizeHandle).toHaveCount(2);

    // Here we simulate a resize start on Task 4 and quickly enter Task 7
    // The resize handle should not be added to Task 7
    await pointerDown(SELECTORS.resizeEndHandle);
    await hover(getPillWrapper("Task 4"));

    expect(getPillWrapper("Task 7").querySelectorAll(SELECTORS.resizeHandle)).toHaveCount(2);
    expect(getPillWrapper("Task 4").querySelectorAll(SELECTORS.resizeHandle)).toHaveCount(0);
});

test("create a task maintains the domain", async () => {
    Tasks._views = { form: '<form><field name="name"/></form>' };
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" plan="false"></gantt>',
        domain: [["user_id", "=", 2]], // I am an important line
    });
    expect(SELECTORS.pill).toHaveCount(3);
    await hoverGridCell("06", "December 2018");
    await clickCell("06", "December 2018");

    await contains(".modal [name=name] input").edit("new task");
    await contains(".modal .o_form_button_save").click();
    expect(SELECTORS.pill).toHaveCount(3);
});

test("pill is updated after failed resized", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    onRpc("write", () => {
        expect.step("write");
        return true;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 7]],
    });

    const initialPillWidth = getPillWrapper("Task 7").getBoundingClientRect().width;

    // resize to one cell larger (1 day)
    await resizePill(getPillWrapper("Task 7"), "end", +1);

    expect(initialPillWidth).toBe(getPillWrapper("Task 7").getBoundingClientRect().width);

    expect.verifySteps(["get_gantt_data", "write", "get_gantt_data"]);
});

test("move a pill in the same row (Manual Reschedule) and undo", async () => {
    expect.assertions(9);

    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([7], { message: "should write on the correct record" });
        expect(args[1]).toEqual(
            {
                start: "2018-12-21 12:30:12",
                stop: "2018-12-21 18:29:59",
            },
            { message: "both start and stop date should be correctly set (+1 day)" }
        );
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 7]],
    });

    expect(getPillWrapper("Task 7")).toHaveClass(CLASSES.draggable);
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);

    // move a pill in the next cell (+1 day)
    const { moveTo, drop } = await dragPill("Task 7");
    await moveTo({ columnHeader: "21", groupHeader: "December 2018", part: 2 });
    expect(SELECTORS.startBadge).toHaveText("12/21/2018, 1:30 PM");
    expect(SELECTORS.stopBadge).toHaveText("12/21/2018, 7:29 PM");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
    ]);
});

test("move a pill in the same row (with different timezone)", async () => {
    expect.assertions(8);

    patchWithCleanup(luxon.Settings, {
        defaultZone: luxon.IANAZone.create("Europe/Brussels"),
    });

    Tasks._records[7].start = `${DST_DATES.winterToSummer.before} 05:00:00`;
    Tasks._records[7].stop = `${DST_DATES.winterToSummer.before} 06:30:00`;

    onRpc(({ args, method }) => {
        if (method === "write") {
            expect.step("write");
            expect(args).toEqual([
                [8],
                {
                    start: `${DST_DATES.winterToSummer.after} 04:00:00`,
                    stop: `${DST_DATES.winterToSummer.after} 05:30:00`,
                },
            ]);
        }
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        domain: [["id", "=", 8]],
        context: {
            initialDate: `${DST_DATES.winterToSummer.before} 08:00:00`,
        },
    });

    await contains(".o_gantt_scroll_container").scroll({ x: 300 });
    expect(getGridContent().rows).toEqual([
        {
            pills: [{ title: "Task 8", level: 0, colSpan: "30 March 2019 -> 30 (1/2) March 2019" }],
        },
    ]);

    // +1 day -> move beyond the DST switch
    const { moveTo, drop } = await dragPill("Task 8");
    await moveTo({ columnHeader: "31", groupHeader: "March 2019", part: 1 });
    expect(SELECTORS.startBadge).toHaveText("3/31/2019, 6:00 AM");
    expect(SELECTORS.stopBadge).toHaveText("3/31/2019, 7:30 AM");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();

    expect(getGridContent().rows).toEqual([
        {
            pills: [{ title: "Task 8", level: 0, colSpan: "31 March 2019 -> 31 (1/2) March 2019" }],
        },
    ]);
    expect.verifySteps(["write"]);
});

test("move a pill in another row", async () => {
    expect.assertions(4);

    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([7], { message: "should write on the correct record" });
        expect(args[1]).toEqual(
            {
                project_id: 1,
                start: "2018-12-21 12:30:12",
                stop: "2018-12-21 18:29:59",
            },
            { message: "all modified fields should be correctly set" }
        );
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
        domain: [["id", "in", [1, 7]]],
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);

    // move a pill (task 7) in the other row and in the the next cell (+1 day)
    const { drop } = await dragPill("Task 7");
    await drop({ columnHeader: "21", groupHeader: "December 2018", part: 2, row: "Project 1" });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 7",
                    level: 1,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
    ]);
});

test("undo action: move a pill in another row", async () => {
    expect.assertions(8);

    onRpc("gantt_undo_drag_drop", function ({ model, args }) {
        expect(args[0]).toEqual(7);
        expect(args[1]).toEqual("reschedule");
        expect(args[2]).toEqual(
            {
                project_id: 2,
                start: "2018-12-20 12:30:12",
                stop: "2018-12-20 18:29:59",
            },
            { message: "all modified fields should be correctly set back to their initial values" }
        );
        return this.env[model].write([args[0]], args[2]);
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
        domain: [["id", "in", [1, 7]]],
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    const initialGridContent = [
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ];
    expect(getGridContent().rows).toEqual(initialGridContent);

    // move a pill (task 7) in the other row and in the the next cell (+1 day)
    const { drop } = await dragPill("Task 7");
    await drop({ columnHeader: "21", groupHeader: "December 2018", part: 2, row: "Project 1" });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 7",
                    level: 1,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
    ]);
    expect(".o_notification_content").toHaveText("Record rescheduled");

    // undo the rescheduling of the pill
    await contains(".o_notification_buttons button i[title='Undo']").click();
    expect(getGridContent().rows).toEqual(initialGridContent, {
        message: "the pill should be back to its initial state",
    });
    expect(".o_notification_content").toHaveText("Record reschedule undone");
});

test("undo action: move a pill in another row (groupby m2m)", async () => {
    expect.assertions(8);
    onRpc("gantt_undo_drag_drop", function ({ model, args }) {
        expect(args[0]).toEqual(7);
        expect(args[1]).toEqual("reschedule");
        expect(args[2]).toEqual(
            {
                resource_ids: [2, 3],
                start: "2018-12-20 12:30:12",
                stop: "2018-12-20 18:29:59",
            },
            { message: "all modified fields should be correctly set back to their initial values" }
        );
        return this.env[model].write([args[0]], args[2]);
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["resource_ids"],
        domain: [["id", "in", [1, 7]]],
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    const initialGridContent = [
        {
            title: "Undefined Resources",
        },
        {
            title: "Resource 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Resource 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
        {
            title: "Resource 3",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ];
    expect(getGridContent().rows).toEqual(initialGridContent);

    // move a pill (task 1) in the other row and in the the next cell (+1 day)
    const { drop } = await dragPill("Task 7");
    await drop({ columnHeader: "21", groupHeader: "December 2018", part: 2, row: "Resource 1" });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Resources",
        },
        {
            title: "Resource 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 7",
                    level: 1,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
    ]);
    expect(".o_notification_content").toHaveText("Record rescheduled");

    // undo the rescheduling of the pill
    await contains(".o_notification_buttons button i[title='Undo']").click();
    expect(getGridContent().rows).toEqual(initialGridContent, {
        message: "the pill should be back to its initial state",
    });
    expect(".o_notification_content").toHaveText("Record reschedule undone");
});

test("copy a pill in another row", async () => {
    expect.assertions(10);
    onRpc("copy", ({ args, kwargs }) => {
        expect(args[0]).toEqual([7], { message: "should copy the correct record" });
        expect(kwargs.default).toEqual(
            {
                start: "2018-12-21 12:30:12",
                stop: "2018-12-21 18:29:59",
                project_id: 1,
            },
            { message: "should use the correct default values when copying" }
        );
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
        domain: [["id", "in", [1, 7, 9]]], // 9 will be the newly created record
    });

    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);

    await keyDown("Control");

    // move a pill (task 7) in the other row and in the the next cell (+1 day)
    const { drop, moveTo } = await dragPill("Task 7");
    await moveTo({ columnHeader: "21", groupHeader: "December 2018", part: 2, row: "Project 1" });

    expect(SELECTORS.renderer).toHaveClass("o_copying");

    await keyUp("Control");

    expect(SELECTORS.renderer).toHaveClass("o_grabbing");

    await keyDown("Control");
    expect(SELECTORS.startBadge).toHaveText("12/21/2018, 1:30 PM");
    expect(SELECTORS.stopBadge).toHaveText("12/21/2018, 7:29 PM");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 7 (copy)",
                    level: 1,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);
});

test("undo action: copy a pill in another row", async () => {
    expect.assertions(8);

    onRpc("gantt_undo_drag_drop", function ({ model, args }) {
        expect(args[0]).toEqual(9);
        expect(args[1]).toEqual("copy");
        expect(args[2]).toEqual({}, { message: "no fallback data is needed to undo the copy" });
        return this.env[model].unlink([args[0]]);
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
        domain: [["id", "in", [1, 7, 9]]], // 9 will be the newly created record
    });

    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    const initialGridContent = [
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ];
    expect(getGridContent().rows).toEqual(initialGridContent);

    // move a pill (task 7) in the other row and in the the next cell (+1 day)
    await keyDown("Control");
    const { drop } = await dragPill("Task 7");
    await drop({ columnHeader: "21", groupHeader: "December 2018", part: 2, row: "Project 1" });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 7 (copy)",
                    level: 1,
                    colSpan: "21 (1/2) December 2018 -> 21 December 2018",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);
    expect(".o_notification_content").toHaveText("Record duplicated");

    // undo the copy of the pill
    await contains(".o_notification_buttons button i[title='Undo']").click();
    expect(getGridContent().rows).toEqual(initialGridContent, {
        message: "the pill should be back to its initial state",
    });
    expect(".o_notification_content").toHaveText("Record removed");
});

test("copy a pill in another row, but in the same column", async () => {
    expect.assertions(2);
    onRpc("copy", ({ args, kwargs }) => {
        expect(args[0]).toEqual([7], { message: "should copy the correct record" });
        expect(kwargs.default).toEqual(
            {
                start: "2018-12-20 12:30:12",
                stop: "2018-12-20 18:29:59",
                project_id: 1,
            },
            { message: "the dates should be copied explicitely" }
        );
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
    });

    await keyDown("Control");
    const { drop } = await dragPill("Task 7");
    await drop({ columnHeader: "20", groupHeader: "December 2018", part: 2, row: "Project 1" });
    await keyUp("Control");
});

test("move a pill in another row in multi-level grouped", async () => {
    onRpc("write", ({ args }) => {
        expect(args).toEqual([[7], { project_id: 1 }], {
            message: "should only write on user_id on the correct record",
        });
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["user_id", "project_id", "stage"],
        domain: [["id", "in", [3, 7]]],
    });

    expect(`${SELECTORS.pillWrapper}${SELECTORS.draggable}`).toHaveCount(2);
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "Undefined Stage",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [{ title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" }],
        },
        {
            title: "Cancelled",
            pills: [
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" }],
        },
        {
            title: "Cancelled",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
    ]);

    // move a pill (task 7) in the top-level group (User 2)
    const { drop } = await dragPill("Task 7");
    await drop({ row: "Cancelled", columnHeader: "20", groupHeader: "December 2018", part: 2 });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "Undefined Stage",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Cancelled",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ]);
});

test("move a pill in another row in multi-level grouped (many2many case)", async () => {
    expect.assertions(5);

    Tasks._fields.user_ids = fields.Many2many({ string: "Assignees", relation: "res.users" });
    Tasks._records[1].user_ids = [1, 2];

    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([2], { message: "should write on the correct record" });
        expect(args[1]).toEqual({ user_ids: false }, { message: "should write these changes" });
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["user_id", "project_id", "user_ids"],
        domain: [
            ["user_id", "=", 2],
            ["project_id", "=", 1],
        ],
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 500 });

    // sanity check
    expect(queryAllTexts(`${SELECTORS.pillWrapper}${SELECTORS.draggable}`)).toEqual([
        "Task 3",
        "Task 2",
        "Task 2",
    ]);
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "Undefined Assignees",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Undefined Assignees",
            pills: [
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "User 1",
            pills: [
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
            ],
        },
        {
            title: "User 2",
            pills: [
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
            ],
        },
    ]);

    // move a pill (first task 2) in "Undefined Assignees"
    const { drop } = await dragPill("Task 2", { nth: 1 });
    await drop({
        row: "Undefined Assignees",
        num: 2,
        columnHeader: "17",
        groupHeader: "December 2018",
        part: 2,
    });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "Undefined Assignees",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Undefined Assignees",
            pills: [
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ]);
});

test("grey pills should not be resizable nor draggable", async () => {
    expect.assertions(4);

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" color="color" />',
        groupBy: ["user_id", "project_id"],
        domain: [["id", "=", 7]],
    });

    const groupPill = queryOne(`${SELECTORS.pillWrapper}.o_gantt_group_pill`);
    expect(groupPill).not.toHaveClass(CLASSES.resizable);
    expect(groupPill).not.toHaveClass(CLASSES.draggable);

    const rowPill = queryOne(`${SELECTORS.pillWrapper}:not(.o_gantt_group_pill)`);
    expect(rowPill).toHaveClass(CLASSES.resizable);
    expect(rowPill).toHaveClass(CLASSES.draggable);
});

test("should not be draggable when disable_drag_drop is set", async () => {
    expect.assertions(1);

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" color="color" disable_drag_drop="1" />',
        groupBy: ["user_id", "project_id"],
        domain: [["id", "=", 7]],
    });

    expect(SELECTORS.draggable).toHaveCount(0);
});

test("view reload when period changes", async () => {
    let reloadCount = 0;
    onRpc("get_gantt_data", () => {
        reloadCount++;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" display_unavailability="1" />',
    });

    expect(reloadCount).toBe(1, { message: "view should have loaded" });

    await selectCustomRange({ startDate: "2019-01-01", stopDate: "2019-02-28" });
    expect(reloadCount).toBe(2);

    await selectCustomRange({ startDate: "2019-01-01", stopDate: "2019-01-31" });
    expect(reloadCount).toBe(3);
});

test("unavailabilities should not be reloaded when period changes if display_unavailability is not set", async () => {
    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step("get_gantt_data");
        expect(kwargs.unavailability_fields).toEqual([]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" />',
    });

    expect.verifySteps(["get_gantt_data"]);

    await selectCustomRange({ startDate: "2019-01-01", stopDate: "2019-02-28" });
    expect.verifySteps(["get_gantt_data"]);

    await selectCustomRange({ startDate: "2019-01-01", stopDate: "2019-01-31" });
    expect.verifySteps(["get_gantt_data"]);
});

test("close tooltip when drag pill", async () => {
    Tasks._records[1].start = "2018-12-16 03:00:00";

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt default_range="week" date_start="start" date_stop="stop" />',
    });

    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 1",
                    colSpan: "Out of bounds (1)  -> Out of bounds (43) ",
                    level: 0,
                },
                {
                    title: "Task 2",
                    colSpan:
                        "Sunday 16 Week 51, Dec 16 - Dec 22 -> Saturday 22 (1/2) Week 51, Dec 16 - Dec 22",
                    level: 1,
                },
                {
                    title: "Task 4",
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 (1/2) Week 51, Dec 16 - Dec 22",
                    level: 2,
                },
                {
                    title: "Task 7",
                    colSpan:
                        "Thursday 20 (1/2) Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                    level: 2,
                },
            ],
        },
    ]);
    // open popover
    await contains(getPill("Task 4")).click();
    await runAllTimers();
    await waitFor(".o_popover");

    // enable the drag feature and move the pill
    const { drop, moveTo } = await drag(getPillWrapper("Task 4"));
    await animationFrame();
    expect(".o_popover").toHaveCount(1, {
        message: "popover should still be opened as the pill did not move yet",
    });
    await moveTo(getPillWrapper("Task 2"));
    await waitForNone(".o_popover");
    expect(".o_popover").toHaveCount(0, {
        message: "popover should have been closed",
    });
    await drop();
});

test("drag&drop on other pill in grouped view", async () => {
    Tasks._records[0].start = "2018-12-16 05:00:00";
    Tasks._records[0].stop = "2018-12-16 07:00:00";
    Tasks._records[1].stop = "2018-12-17 13:00:00";

    const def = Promise.withResolvers();
    onRpc("write", () => def.promise);

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt default_range="week" date_start="start" date_stop="stop" />',
        groupBy: ["project_id"],
    });

    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 1",
                    level: 0,
                    colSpan:
                        "Sunday 16 Week 51, Dec 16 - Dec 22 -> Sunday 16 (1/2) Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan:
                        "Monday 17 (1/2) Week 51, Dec 16 - Dec 22 -> Monday 17 Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 4",
                    level: 0,
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 (1/2) Week 51, Dec 16 - Dec 22",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan:
                        "Thursday 20 (1/2) Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                },
            ],
        },
    ]);
    await contains(getPill("Task 2")).click();
    await runAllTimers();
    await waitFor(".o_popover");

    const { drop } = await dragPill("Task 2");
    await drop({ pill: "Task 1" });

    await contains(document.body).click(); // To simulate the full 'pointerup' sequence

    def.resolve();
    await animationFrame();

    expect(".popover").toHaveCount(0);
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 2",
                    level: 0,
                    colSpan:
                        "Sunday 16 Week 51, Dec 16 - Dec 22 -> Sunday 16 (1/2) Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 1",
                    level: 1,
                    colSpan:
                        "Sunday 16 Week 51, Dec 16 - Dec 22 -> Sunday 16 (1/2) Week 51, Dec 16 - Dec 22",
                },
                {
                    title: "Task 4",
                    level: 0,
                    colSpan:
                        "Thursday 20 Week 51, Dec 16 - Dec 22 -> Thursday 20 (1/2) Week 51, Dec 16 - Dec 22",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan:
                        "Thursday 20 (1/2) Week 51, Dec 16 - Dec 22 -> Thursday 20 Week 51, Dec 16 - Dec 22",
                },
            ],
        },
    ]);
});

test("disable drop of pill on groups by readonly field", async () => {
    // Group "Work Order" by: color > cost (readonly) > employee > size
    // Pills can be only be dropped in the same "child groups" (employee & size)
    // or any group above the highest readonly parent (color)
    await mountGanttView({
        resModel: "workorders",
        arch: '<gantt date_start="start" date_stop="stop" />',
        groupBy: ["color", "cost", "employee", "size"],
    });

    /*  Structure is the following:

        color (1)
        └── cost (86)
            ├── employee (Jordan)
            │   └── size (198) --> Work Order 1
            └── employee (Michael)
                └── size (198) --> Work Order 3
        color (2)
        └── cost (420)
            └── employee (Jordan)
                └── size (183) --> Work Order 2

        Before drag, all but color rows should have the readonly class.
    */
    expect(cssClassPresencePerCellInColumn("o_gantt_readonly", ["16", "December 2018"])).toEqual([
        false, // "Undefined Color" is not readonly
        true, // "Undefined Cost" is readonly
        true, // "Undefined Employee" is not readonly but parent "cost" is
        true, // "Undefined Size" is not readonly but parent "cost" is
        false, // "color" is not readonly
        true, // "cost" is readonly
        true, // "employee"(Jordan) is not readonly but parent "cost" is
        true, // "size"(198) is not readonly but parent "cost" is
        true, // "employee"(Michael) is not readonly but parent "cost" is
        true, // "size"(198) is not readonly but parent "cost" is
        false, // "color" is not readonly
        true, // "cost" is readonly
        true, // "employee" is not readonly but parent "cost" is
        true, // "size" is not readonly but parent "cost" is
    ]);

    const { drop, moveTo } = await dragPill("Work Order 1");
    await moveTo({ pill: "Work Order 3" });
    await advanceTime(20); // Pointer move is subjected to throttleForAnimation in gantt

    // // During drag, the user should be able to drop in
    // //  - the child groups (employee & size), so rows 3 to 6
    // //  - the group above the highest readonly parent (color), so rows 1 & 7
    // // The (empty) "Undefined X" chain is a separate, untouched subtree.
    expect(cssClassPresencePerCellInColumn("o_gantt_readonly", ["16", "December 2018"])).toEqual([
        false,
        true,
        true,
        true,
        false,
        true,
        false, // part of child group
        false, // original row of the pill
        false, // part of child group
        false, // part of child group
        false,
        true,
        true, // NOT part of the child group so should remain readonly
        true, // NOT part of the child group so should remain readonly
    ]);

    await drop({ pill: "Work Order 3" });
    await advanceTime(20);

    /*  After drop, structure should be the following:

        color (1)
        └── cost (86)
            └── employee (Michael)
                └── size (198) --> Work Order 1 & Work Order 3
        color (2)
        └── cost (420)
            └── employee (Jordan)
                └── size (183) --> Work Order 2

        Again, all but color rows should have the readonly class
    */
    expect(cssClassPresencePerCellInColumn("o_gantt_readonly", ["16", "December 2018"])).toEqual([
        false,
        true,
        true,
        true,
        false,
        true,
        true,
        true,
        false,
        true,
        true,
        true,
    ]);
});

test("display mode button", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_mode="sparse"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(SELECTORS.dense).toHaveCount(1);
    expect(SELECTORS.sparse).toHaveCount(0);

    const rowsInSparseMode = [
        {
            title: "Task 5",
        },
        {
            title: "Task 1",
            pills: [
                { title: "Task 1", level: 0, colSpan: "Out of bounds (1)  -> 31 December 2018" },
            ],
        },
        {
            title: "Task 2",
            pills: [
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
            ],
        },
        {
            title: "Task 4",
            pills: [
                {
                    title: "Task 4",
                    level: 0,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
            ],
        },
        {
            title: "Task 7",
            pills: [
                {
                    title: "Task 7",
                    level: 0,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
            ],
        },
        {
            title: "Task 3",
            pills: [
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ];

    expect(getGridContent().rows).toEqual(rowsInSparseMode);

    await click(SELECTORS.dense);
    await animationFrame();
    expect(SELECTORS.dense).toHaveCount(0);
    expect(SELECTORS.sparse).toHaveCount(1);

    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 1",
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 1,
                },
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 2,
                },
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 2,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                },
            ],
        },
    ]);

    await click(SELECTORS.sparse);
    await animationFrame();
    expect(SELECTORS.dense).toHaveCount(1);
    expect(SELECTORS.sparse).toHaveCount(0);

    expect(getGridContent().rows).toEqual(rowsInSparseMode);

    expect.verifySteps([]);
});

test("display mode button and 'Expand rows'/'Collapse rows' buttons", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id,project_id"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);

    const rowsInDenseMode = [
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "Out of bounds (8)  -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> 31 December 2018" },
            ],
        },
        {
            title: "Project 1",
            pills: [
                { title: "Task 1", colSpan: "Out of bounds (1)  -> 31 December 2018", level: 0 },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
            ],
        },
        {
            title: "Project 2",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                { title: "Task 3", colSpan: "27 December 2018 -> 03 (1/2) January 2019", level: 0 },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
    ];

    const rowsInSparseMode = [
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "",
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "Out of bounds (8)  -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> 31 December 2018" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "Out of bounds (1)  -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> 31 December 2018" },
            ],
        },
        {
            title: "Task 1",
            pills: [
                { title: "Task 1", colSpan: "Out of bounds (1)  -> 31 December 2018", level: 0 },
            ],
        },
        {
            title: "Task 4",
            pills: [
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "Project 2",
            isGroup: true,
        },
        {
            title: "Task 5",
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "Task 2",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
            ],
        },
        {
            title: "Task 3",
            pills: [
                { title: "Task 3", colSpan: "27 December 2018 -> 03 (1/2) January 2019", level: 0 },
            ],
        },
        {
            title: "Project 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" }],
        },
        {
            title: "Task 7",
            pills: [
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
    ];

    const rowsInCollapsedMode = [
        {
            title: "Undefined Assign To",
            isGroup: true,
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "Out of bounds (8)  -> 19 December 2018" },
                { title: "2", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "1", colSpan: "20 (1/2) December 2018 -> 31 December 2018" },
            ],
        },
        {
            title: "User 2",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 20 December 2018" },
                { title: "1", colSpan: "21 December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ];

    expect(getGridContent().rows).toEqual(rowsInDenseMode);

    await click(SELECTORS.collapseButton);
    await animationFrame();
    expect(SELECTORS.expandButton).toHaveCount(1);
    expect(SELECTORS.collapseButton).toHaveCount(0);
    expect(getGridContent().rows).toEqual(rowsInCollapsedMode);

    await click(SELECTORS.sparse);
    await animationFrame();
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows).toEqual(rowsInSparseMode);

    await click(SELECTORS.collapseButton);
    await animationFrame();
    expect(SELECTORS.expandButton).toHaveCount(1);
    expect(SELECTORS.collapseButton).toHaveCount(0);
    expect(getGridContent().rows).toEqual(rowsInCollapsedMode);

    await click(SELECTORS.dense);
    await animationFrame();
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows).toEqual(rowsInDenseMode);

    expect.verifySteps([]);
});

test("rows expanded after a grouby change", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="project_id,user_id"/>`,
        searchViewArch: `
            <search>
                <filter name="goup_by_project_id" string="Project" context="{'group_by':'project_id'}" />
            </search>
        `,
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
            isGroup: true,
        },
        {
            title: "Undefined Assign To",
        },
        {
            title: "Project 1",
            isGroup: true,
            pills: [
                { title: "1", colSpan: "Out of bounds (1)  -> 17 (1/2) December 2018" },
                { title: "2", colSpan: "17 (1/2) December 2018 -> 19 December 2018" },
                { title: "3", colSpan: "20 December 2018 -> 20 (1/2) December 2018" },
                { title: "2", colSpan: "20 (1/2) December 2018 -> 22 (1/2) December 2018" },
                { title: "1", colSpan: "22 (1/2) December 2018 -> 26 December 2018" },
                { title: "2", colSpan: "27 December 2018 -> 31 December 2018" },
                { title: "1", colSpan: "01 January 2019 -> 03 (1/2) January 2019" },
            ],
        },
        {
            title: "User 1",
            pills: [
                { title: "Task 1", colSpan: "Out of bounds (1)  -> 31 December 2018", level: 0 },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
            ],
        },
        {
            title: "User 2",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                { title: "Task 3", colSpan: "27 December 2018 -> 03 (1/2) January 2019", level: 0 },
            ],
        },
        {
            title: "Project 2",
            isGroup: true,
            pills: [{ title: "1", colSpan: "20 (1/2) December 2018 -> 20 December 2018" }],
        },
        {
            title: "User 1",
        },
        {
            title: "User 2",
            pills: [
                {
                    title: "Task 7",
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                },
            ],
        },
    ]);

    await click(SELECTORS.collapseButton);
    await animationFrame();
    expect.verifySteps([]);
    expect(SELECTORS.expandButton).toHaveCount(1);
    expect(SELECTORS.collapseButton).toHaveCount(0);
    expect(getGridContent().rows).toEqual([
        {
            isGroup: true,
            title: "Undefined Project",
        },
        {
            isGroup: true,
            pills: [
                { colSpan: "Out of bounds (1)  -> 17 (1/2) December 2018", title: "1" },
                { colSpan: "17 (1/2) December 2018 -> 19 December 2018", title: "2" },
                { colSpan: "20 December 2018 -> 20 (1/2) December 2018", title: "3" },
                { colSpan: "20 (1/2) December 2018 -> 22 (1/2) December 2018", title: "2" },
                { colSpan: "22 (1/2) December 2018 -> 26 December 2018", title: "1" },
                { colSpan: "27 December 2018 -> 31 December 2018", title: "2" },
                { colSpan: "01 January 2019 -> 03 (1/2) January 2019", title: "1" },
            ],
            title: "Project 1",
        },
        {
            isGroup: true,
            pills: [{ colSpan: "20 (1/2) December 2018 -> 20 December 2018", title: "1" }],
            title: "Project 2",
        },
    ]);

    await toggleSearchBarMenu();
    await toggleMenuItem("Project");
    await animationFrame();
    expect.verifySteps(["get_gantt_data"]);
    expect(SELECTORS.expandButton).toHaveCount(0);
    expect(SELECTORS.collapseButton).toHaveCount(1);
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            pills: [
                { colSpan: "Out of bounds (1)  -> 31 December 2018", level: 0, title: "Task 1" },
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 1,
                    title: "Task 2",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 2,
                    title: "Task 4",
                },
                { colSpan: "27 December 2018 -> 03 (1/2) January 2019", level: 1, title: "Task 3" },
            ],
            title: "Project 1",
        },
        {
            pills: [
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 7",
                },
            ],
            title: "Project 2",
        },
    ]);
});

test("unavailabilities fetched with right parameters", async () => {
    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step(Object.values(pick(kwargs, "start_date", "stop_date", "scale")));
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day"/>`,
    });
    expect.verifySteps([["2018-12-18 23:00:00", "2018-12-21 23:00:00", "day"]]);

    await selectRange("Week");
    await ganttControlsChanges();
    expect.verifySteps([["2018-12-08 23:00:00", "2018-12-29 23:00:00", "week"]]);

    await selectRange("Month");
    await ganttControlsChanges();
    expect.verifySteps([["2018-10-31 23:00:00", "2019-01-31 23:00:00", "month"]]);

    await selectRange("Quarter");
    await ganttControlsChanges();
    expect.verifySteps([["2018-06-30 23:00:00", "2019-03-31 23:00:00", "month"]]);

    await selectRange("Year");
    await ganttControlsChanges();
    expect.verifySteps([["2016-12-31 23:00:00", "2019-12-31 23:00:00", "year"]]);

    await selectCustomRange({ startDate: "2018-12-31", stopDate: "2019-06-15" });
    expect.verifySteps([["2018-12-30 23:00:00", "2019-06-15 23:00:00", "month"]]);
});

test("total progress bar displayed", async () => {
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        const result = parent();
        result.progress_bars.user_id = {
            1: { value: 50, max_value: 100 },
            2: { value: 25, max_value: 200 },
        };
        result.progress_bars.__default = {
            false: { value: 75, max_value: 300 },
        };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" default_group_by="user_id" progress_bar="user_id" total_row="1" default_range="month" precision="{'month':'day:half'}">
                <field name="user_id"/>
            </gantt>
        `,
    });
    expect(SELECTORS.rowTotalProgressBar).toHaveStyle("width: 25%", { inline: true });
});

test("progress bars fetched with the right start/stop dates", async () => {
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        const result = parent();
        expect.step([kwargs.start_date, kwargs.stop_date]);
        result.progress_bars.user_id = {
            1: { value: 50, max_value: 100 },
            2: { value: 25, max_value: 200 },
        };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" default_group_by="user_id" progress_bar="user_id" default_range="day" >
                <field name="user_id"/>
            </gantt>
        `,
    });
    expect.verifySteps([["2018-12-18 23:00:00", "2018-12-21 23:00:00"]]);

    await selectRange("Week");
    await ganttControlsChanges();
    expect.verifySteps([["2018-12-08 23:00:00", "2018-12-29 23:00:00"]]);

    await selectRange("Month");
    await ganttControlsChanges();
    expect.verifySteps([["2018-10-31 23:00:00", "2019-01-31 23:00:00"]]);

    await selectRange("Quarter");
    await ganttControlsChanges();
    expect.verifySteps([["2018-06-30 23:00:00", "2019-03-31 23:00:00"]]);

    await selectRange("Year");
    await ganttControlsChanges();
    expect.verifySteps([["2016-12-31 23:00:00", "2019-12-31 23:00:00"]]);

    await selectCustomRange({ startDate: "2018-12-31", stopDate: "2019-06-15" });
    expect.verifySteps([["2018-12-30 23:00:00", "2019-06-15 23:00:00"]]);
});

test("focus today with scroll (in range & outside)", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    expect.verifySteps(["get_gantt_data"]);
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    expect(queryOne(".o_gantt_cell.o_gantt_today")).toBe(getCell("20", "December 2018"));
    let { columnHeaders } = getGridContent();
    expect(columnHeaders).toHaveLength(29);
    expect(columnHeaders[0].title).toBe("01"); // December
    expect(columnHeaders.at(-1).title).toBe("29"); // December

    await scroll(".o_gantt_scroll_container", { left: 800 });
    await animationFrame();

    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    columnHeaders = getGridContent().columnHeaders;
    expect(columnHeaders).toHaveLength(33);
    expect(columnHeaders[0].title).toBe("13"); // December
    expect(columnHeaders.at(-1).title).toBe("14"); // January

    await focusToday();
    await ganttControlsChanges();

    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    columnHeaders = getGridContent().columnHeaders;
    expect(columnHeaders).toHaveLength(32);
    expect(columnHeaders[0].title).toBe("04"); // December
    expect(columnHeaders.at(-1).title).toBe("04"); // January

    await scroll(".o_gantt_scroll_container", { left: 2000 });
    await animationFrame();

    expect(".o_gantt_cell.o_gantt_today").not.toHaveCount();
    columnHeaders = getGridContent().columnHeaders;
    expect(columnHeaders).toHaveLength(33);
    expect(columnHeaders[0].title).toBe("05"); // January
    expect(columnHeaders.at(-1).title).toBe("06"); // February

    await focusToday();
    await ganttControlsChanges();
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    columnHeaders = getGridContent().columnHeaders;
    expect(columnHeaders).toHaveLength(32);
    expect(columnHeaders[0].title).toBe("04"); // December
    expect(columnHeaders.at(-1).title).toBe("04"); // January
});

test("focus today with range change (in range & outside)", async () => {
    onRpc("get_gantt_data", () => {
        expect.step("get_gantt_data");
    });
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    expect.verifySteps(["get_gantt_data"]);
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    expect(queryOne(".o_gantt_cell.o_gantt_today")).toBe(getCell("20", "December 2018"));
    let gridContent = getGridContent();
    expect(gridContent.range).toBe("12/01/2018 -> 02/28/2019");
    expect(gridContent.columnHeaders).toHaveLength(29);
    expect(gridContent.columnHeaders[0].title).toBe("01"); // December
    expect(gridContent.columnHeaders.at(-1).title).toBe("29"); // December

    await selectCustomRange({ startDate: "2018-11-15", stopDate: "2019-02-15" });
    expect.verifySteps(["get_gantt_data"]);
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    expect(queryOne(".o_gantt_cell.o_gantt_today")).toBe(getCell("20", "December 2018"));
    gridContent = getGridContent();
    expect(gridContent.range).toBe("11/15/2018 -> 02/15/2019");
    expect(gridContent.columnHeaders).toHaveLength(32);
    expect(gridContent.columnHeaders[0].title).toBe("28"); // November
    expect(gridContent.columnHeaders.at(-1).title).toBe("29"); // December

    await focusToday();
    await ganttControlsChanges();
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    gridContent = getGridContent();
    expect(gridContent.columnHeaders).toHaveLength(32);
    expect(gridContent.columnHeaders[0].title).toBe("04"); // December
    expect(gridContent.columnHeaders.at(-1).title).toBe("04"); // January

    await selectCustomRange({ startDate: "2019-01-01", stopDate: "2019-02-28" });
    expect(getGridContent().range).toBe("01/01/2019 -> 02/28/2019");
    expect.verifySteps(["get_gantt_data"]);
    expect(".o_gantt_cell.o_gantt_today").not.toHaveCount();

    await focusToday();
    await ganttControlsChanges();
    expect.verifySteps(["get_gantt_data"]);
    expect(".o_gantt_cell.o_gantt_today").toBeVisible();
    expect(getGridContent().range).toBe("11/21/2018 -> 01/17/2019");
});

test("set start/stop date: should keep focused date", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    // set focus around 23 January 2019
    await scroll(".o_gantt_scroll_container", { left: 2000 });
    await animationFrame();
    await selectCustomRange({ startDate: "2018-12-01", stopDate: "2019-05-28" });
    expect(getCell("23", "January 2019")).toBeVisible();
    await selectCustomRange({ startDate: "2019-01-22", stopDate: "2019-05-28" });
    expect(getCell("23", "January 2019")).toBeVisible();
    await selectCustomRange({ startDate: "2018-12-01", stopDate: "2019-01-22" });
    expect(getCell("22", "January 2019")).toBeVisible();
});

test("focus first pill on row header click", async () => {
    Tasks._records = [
        {
            id: 1,
            name: "Task 1",
            start: "2018-11-30 23:00:00",
            stop: "2018-12-01 23:00:00",
            user_id: 1,
        },
        {
            id: 2,
            name: "Task 2",
            start: "2019-02-27 23:00:00",
            stop: "2019-02-28 23:00:00",
            user_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>',
    });
    // set focus around 23 January 2019
    await scroll(".o_gantt_scroll_container", { left: 2000 });
    await animationFrame();
    expect(SELECTORS.pill).toHaveCount(0);

    // the first row header is the always-present "Undefined Assign To" group; "User 1" is the second
    await click(`${SELECTORS.rowHeader}:eq(1)`);
    await animationFrame();
    expect(SELECTORS.pill).toHaveCount(1);
    expect(SELECTORS.pill).toHaveText("Task 1");
});

test("Select a range via the range menu", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
    });
    let content = getGridContent();
    expect(content.range).toBe("12/01/2018 -> 02/28/2019");

    await selectRange("Day");
    content = getGridContent();
    expect(content.range).toBe("Day");

    await selectRange("Week");
    content = getGridContent();
    expect(content.range).toBe("Week");

    await selectRange("Month");
    content = getGridContent();
    expect(content.range).toBe("Month");

    await selectRange("Quarter");
    content = getGridContent();
    expect(content.range).toBe("Quarter");

    await selectRange("Year");
    content = getGridContent();
    expect(content.range).toBe("Year");
});

test("Select range with left/rigth arrows", async () => {
    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step(kwargs.domain);
    });

    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop" default_range="month"/>',
    });
    await expect.waitForSteps([
        ["&", ["start", "<", "2019-01-31 23:00:00"], ["stop", ">", "2018-10-31 23:00:00"]],
    ]);

    let content = getGridContent();
    expect(content.range).toBe("Month");

    for (let i = 0; i < 3; i++) {
        await click(SELECTORS.nextButton);
    }
    await click(SELECTORS.previousButton);
    await ganttControlsChanges();

    await expect.waitForSteps([
        ["&", ["start", "<", "2019-03-31 23:00:00"], ["stop", ">", "2018-12-31 23:00:00"]],
    ]);
    content = getGridContent();
    expect(content.range).toBe("Month");

    await press("alt+n");
    await ganttControlsChanges();
    await expect.waitForSteps([
        ["&", ["start", "<", "2019-04-30 23:00:00"], ["stop", ">", "2019-01-31 23:00:00"]],
    ]);
    content = getGridContent();
    expect(content.range).toBe("Month");
});

test("make tooltip visible for a long pill", async () => {
    mockDate("2024-03-01 00:00:00");
    Tasks._records.length = 1;
    Tasks._records[0].start = "2024-01-16 00:00:00";
    Tasks._records[0].stop = "2024-11-16 00:00:00";
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt default_range="day" date_start="start" date_stop="stop" />',
        context: {
            default_start_date: "2024-01-01",
            default_stop_date: "2024-12-31",
        },
    });
    const { left: pillLeft, right: pillRight } = getPill("Task 1").getBoundingClientRect();
    expect(pillLeft).toBeLessThan(0);
    expect(pillRight).toBeGreaterThan(window.innerWidth);
    expect(".o_popover").toHaveCount(0);

    await contains(getPill("Task 1")).click();
    await runAllTimers();
    await waitFor(".o_popover");
    const popover = queryOne(".o_popover");
    const { left: popoverLeft, right: popoverRight } = popover.getBoundingClientRect();
    expect(popoverLeft).toBeWithin(0, window.innerWidth);
    expect(popoverRight).toBeWithin(0, window.innerWidth);
});

test("date fields: domain", async () => {
    expect.assertions(5);
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    const domains = [
        ["&", ["start", "<", "2018-12-22"], ["stop", ">=", "2018-12-19"]],
        ["&", ["start", "<", "2018-12-30"], ["stop", ">=", "2018-12-09"]],
        ["&", ["start", "<", "2019-02-01"], ["stop", ">=", "2018-11-01"]],
        ["&", ["start", "<", "2019-04-01"], ["stop", ">=", "2018-07-01"]],
        ["&", ["start", "<", "2020-01-01"], ["stop", ">=", "2017-01-01"]],
    ];
    onRpc("get_gantt_data", ({ kwargs }) => {
        expect(kwargs.domain).toEqual(domains.pop());
    });
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_range="year"/>`,
    });
    await selectRange("Quarter");
    await selectRange("Month");
    await selectRange("Week");
    await selectRange("Day");
});

test("date fields: pill columns", async () => {
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].start = "2018-12-20";
    Tasks._records[0].stop = "2018-12-22";
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "20 December 2018 -> 22 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
});

test.tags("desktop");
test("date fields: resize a pill", async () => {
    expect.assertions(4);
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].start = "2018-12-20";
    Tasks._records[0].stop = "2018-12-22";
    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([1]);
        // initial dates -- start: '"2018-12-20"', stop: '"2018-12-22"'
        expect(args[1]).toEqual({ stop: "2018-12-21" });
    });
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "20 December 2018 -> 22 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
    await resizePill(getPillWrapper("Task 1"), "end", -1);
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "20 December 2018 -> 21 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
});

test("date fields: drag a pill", async () => {
    expect.assertions(4);
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].start = "2018-12-20";
    Tasks._records[0].stop = "2018-12-22";
    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([1]);
        // initial dates -- start: '"2018-12-20"', stop: '"2018-12-22"'
        expect(args[1]).toEqual({ start: "2018-12-19", stop: "2018-12-21" });
    });
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "20 December 2018 -> 22 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
    const { drop } = await dragPill("Task 1");
    await drop({ columnHeader: "19", groupHeader: "December 2018", part: 1 });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "19 December 2018 -> 21 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
});

test("date fields: popover", async () => {
    expect.assertions(4);
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].start = "2018-12-20";
    Tasks._records[0].stop = "2018-12-22";
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    colSpan: "20 December 2018 -> 22 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
        },
    ]);
    expect(".o_popover").toHaveCount(0);
    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(queryAllTexts(".o_popover .o_popover_body div")).toEqual([
        "Start: Dec 20",
        "Stop: Dec 22",
    ]);
    await contains(".o_popover i.oi[data-icon='close']").click();
    expect(".o_popover").toHaveCount(0);
});

test("date fields: dialog", async () => {
    Tasks._fields.start = fields.Date();
    Tasks._fields.stop = fields.Date();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].start = "2018-12-20";
    Tasks._records[0].stop = "2018-12-22";
    Tasks._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="start"/>
                <field name="stop"/>
            </form>
        `,
    };
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    expect(".modal").toHaveCount(0);
    await editPill("Task 1");
    // check that the dialog is opened with prefilled fields
    expect(".modal").toHaveCount(1);
    const modal = queryOne(".modal");
    expect(modal.querySelector(".o_field_widget[name=start] button")).toHaveValue("12/20/2018");
    expect(modal.querySelector(".o_field_widget[name=stop] button")).toHaveValue("12/22/2018");
});

test("gantt popover: on close, reload if record changed", async () => {
    Tasks._fields.user_ids = fields.Many2many({
        string: "Assignees",
        relation: "res.users",
    });
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].user_ids = [1];
    Tasks._views["card,42"] = `
            <card>
                <templates>
                    <t t-name="card">
                        <field name="user_ids" widget="many2many_tags_avatar"/>
                    </t>
                </templates>
            </card>
        `;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"><popover card_id="42"/></gantt>`,
        groupBy: ["user_ids"],
    });
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assignees",
        },
        {
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
            title: "User 1",
        },
    ]);
    expect(`.o_popover`).toHaveCount(0);
    // open gantt popover
    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(`.o_popover`);
    // open avatar field popover
    await contains(".o_popover_body .o_quick_assign", { visible: false }).click();
    // add User 2 to tags
    await contains(
        ".o-overlay-container .o-autocomplete--dropdown-item:contains('User 2')"
    ).click();
    // close avatar field popover
    await press("escape");
    await animationFrame();
    // close gantt popover
    await contains(`.o_popover i.oi[data-icon='close']`).click();
    expect(getGridContent().rows).toEqual([
        {
            title: "Undefined Assignees",
        },
        {
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
            title: "User 1",
        },
        {
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 0,
                    title: "Task 1",
                },
            ],
            title: "User 2",
        },
    ]);
});

test("gantt popover is editable", async function () {
    onRpc("web_save", ({ args }) => {
        expect.step("web_save");
        expect(args[0]).toEqual([5]);
        expect(args[1]).toEqual({ stage: "in_progress" });
    });

    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop">
                <popover>
                    <templates>
                        <t t-name="popover-body">
                            <field name="name"/>
                            <field name="stage" widget="selection"/>
                        </t>
                    </templates>
                </popover>
            </gantt>
        `,
    });
    expect(".o_popover").toHaveCount(0);

    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(".o_popover .o_popover_body .o_field_widget[name=stage] input").toHaveCount(1);
    expect(".o_popover .o_popover_body .o_field_widget[name=stage] input").toHaveValue("Done");

    await editSelectMenu(".o_popover .o_popover_body .o_field_widget[name=stage] input", {
        value: "In Progress",
    });

    expect.verifySteps(["web_save"]);
});

test("gantt popover is readonly if edit='0' is set", async function () {
    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" edit="0">
                <popover>
                    <templates>
                        <t t-name="popover-body">
                            <field name="name"/>
                            <field name="stage" widget="selection"/>
                        </t>
                    </templates>
                </popover>
            </gantt>
        `,
    });
    expect(".o_popover").toHaveCount(0);

    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(".o_popover .o_popover_body .o_field_widget[name=stage]").toHaveText("Done");
});

test("markup html server values", async function () {
    Tasks._fields.description = fields.Html();
    Tasks._records = Tasks._records.slice(0, 1);
    Tasks._records[0].description = `<span>Hello</span>`;

    await mountGanttView({
        type: "gantt",
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop">
                <popover>
                    <templates>
                        <t t-name="popover-body">
                            <field name="description"/>
                        </t>
                    </templates>
                </popover>
            </gantt>
        `,
    });
    expect(".o_popover").toHaveCount(0);

    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(queryAllTexts(".o_popover .o_popover_body")).toEqual(["Hello"]);

    await contains(".o_popover i.oi[data-icon='close']").click();
    expect(".o_popover").toHaveCount(0);
});

test("group header width is capped by available space", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["user_id"],
    });
    const titleWidth = queryRect(".o_gantt_title").width;
    expect(".o_gantt_header_title:first").toHaveStyle({
        maxWidth: document.body.clientWidth - titleWidth,
    });
});

test("edge scrolling on drag ignores row headers", async () => {
    /**
     * @param {string} selector
     * @param {{ x?: number; y?: number }} position
     * @param {() => any} callback
     */
    const dragAndExpect = async (selector, position, callback) => {
        const { drop, moveTo } = await contains(selector).drag();
        await moveTo({ position });
        // Wait for the edge scrolling to scroll to the end
        await advanceFrame(50);
        callback();
        await drop();
    };
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop"/>`,
        groupBy: ["user_id", "project_id", "stage"],
    });
    await scroll(".o_gantt_scroll_container", { left: 300 });
    const rowHeaderWidth = queryRect(".o_gantt_row_headers").width;
    const pill = getPillWrapper("Task 2");
    await hoverPillCell(pill);
    await dragAndExpect(pill, { x: rowHeaderWidth }, () => {
        expect(".o_gantt_scroll_container").toHaveProperty("scrollLeft", 0, {
            message:
                "Should have reached 0 even though the cursor was on the right of the row headers during drag",
        });
    });
});

test("single click on a pill opens the popover only after a 200ms delay", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    await contains(getPill("Task 1")).click();
    expect(".o_popover").toHaveCount(0);
    await advanceTime(200);
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
});

test("double-click on a pill opens the form dialog without opening the popover", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"/>`,
    });
    await dblclick(getPill("Task 1"));
    await animationFrame();
    expect(".o_popover").toHaveCount(0);
    expect(".o_dialog").toHaveCount(1);
});

test("selecting cells to create a task keeps the cells highlighted as long as the popover is displayed", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: '<gantt date_start="start" date_stop="stop"/>',
        groupBy: ["user_id"],
    });

    expect(".o_gantt_pill_wrapper").toHaveCount(5);
    expect(".o_drag_hover").toHaveCount(0);
    expect(".modal").toHaveCount(0);
    await hoverGridCell("11", "December 2018");
    const { moveTo, drop } = await contains(getCell("11", "December 2018")).drag();
    moveTo(getCell("12", "December 2018"));
    await drop();
    expect(".o_gantt_pill_wrapper").toHaveCount(5);
    expect(".o_drag_hover").toHaveCount(1);
    expect(".modal").toHaveCount(1);
    await contains(".o_form_button_save").click();
    expect(".o_gantt_pill_wrapper").toHaveCount(6);
    expect(".o_drag_hover").toHaveCount(0);
    expect(".modal").toHaveCount(0);
});
