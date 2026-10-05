import { beforeEach, describe, expect, test } from "@odoo/hoot";
import {
    click,
    drag,
    leave,
    queryAll,
    queryAllTexts,
    queryFirst,
    queryOne,
    scroll,
    waitFor,
} from "@odoo/hoot-dom";
import { advanceFrame, animationFrame, mockDate, runAllTimers } from "@odoo/hoot-mock";
import { contains, defineParams, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { Tasks, defineGanttModels } from "./gantt_mock_models";
import {
    SELECTORS,
    clickCell,
    dragPill,
    dragToSchedule,
    getCell,
    getCellColorProperties,
    getGridContent,
    getPill,
    getPillBuffer,
    getPillWrapper,
    hoverGridCell,
    hoverPillCell,
    mountGanttView,
    resizePill,
    setCellParts,
} from "./web_gantt_test_helpers";
import { Domain } from "@web/core/domain";

describe.current.tags("desktop");

defineGanttModels();
beforeEach(() => {
    mockDate("2018-12-20T07:00:00", +1);
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
});

test("create attribute", async () => {
    Tasks._views.list = `<list><field name="name"/></list>`;
    Tasks._views.search = `<search><field name="name"/></search>`;
    onRpc("has_group", () => true);
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" create="0"/>`,
    });
    expect(".o_dialog").toHaveCount(0);
    await hoverGridCell("06", "December 2018");
    await clickCell("06", "December 2018");
    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Plan");
    expect(".o_create_button").toHaveCount(0);
});

test("plan attribute", async () => {
    Tasks._views.form = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" plan="0"/>`,
    });
    expect(".o_dialog").toHaveCount(0);
    await hoverGridCell("06", "December 2018");
    await clickCell("06", "December 2018");
    expect(".o_dialog").toHaveCount(1);
    expect(".modal-title").toHaveText("Create");
});

test("edit attribute", async () => {
    Tasks._views.form = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" edit="0"/>`,
    });
    expect(SELECTORS.resizable).toHaveCount(0);
    expect(SELECTORS.draggable).toHaveCount(0);
    expect(getGridContent().rows).toEqual([
        {
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan: "Out of bounds (1)  -> 04 (1/2) December 2018",
                },
                { title: "Task 1", level: 1, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
    ]);

    await contains(getPill("Task 1")).click();
    await runAllTimers();
    await waitFor(".o_popover");
    expect(`.o_popover button.btn-primary`).toHaveText(/view/i);
    await contains(`.o_popover button.btn-primary`).click();
    expect(".modal .o_form_readonly").toHaveCount(1);
});

test("total_row attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" total_row="1"/>`,
    });

    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            pills: [
                {
                    title: "Task 5",
                    level: 0,
                    colSpan: "Out of bounds (1)  -> 04 (1/2) December 2018",
                },
                { title: "Task 1", level: 1, colSpan: "Out of bounds (1)  -> 31 December 2018" },
                {
                    title: "Task 2",
                    level: 0,
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                },
                {
                    title: "Task 4",
                    level: 2,
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                },
                {
                    title: "Task 7",
                    level: 2,
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                },
                { title: "Task 3", level: 0, colSpan: "27 December 2018 -> 03 (1/2) January 2019" },
            ],
        },
        {
            isTotalRow: true,
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 04 (1/2) December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "04 (1/2) December 2018 -> 17 (1/2) December 2018",
                    level: 0,
                    title: "1",
                },
                {
                    colSpan: "17 (1/2) December 2018 -> 19 December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                    title: "3",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "3",
                },
                {
                    colSpan: "21 December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "22 (1/2) December 2018 -> 26 December 2018",
                    level: 0,
                    title: "1",
                },
                {
                    colSpan: "27 December 2018 -> 31 December 2018",
                    level: 0,
                    title: "2",
                },
                {
                    colSpan: "01 January 2019 -> 03 (1/2) January 2019",
                    level: 0,
                    title: "1",
                },
            ],
        },
    ]);
});

test("default_range attribute excluded from scales", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_range="day" scales="week"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("Day");
    expect(columnHeaders).toHaveLength(42);
});

test("default_range omitted, scales provided", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="day,week"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(columnHeaders).toHaveLength(10);

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(`${SELECTORS.scaleSelectorMenu} .dropdown-item`).toHaveCount(3);
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Day",
        "Week",
        "12/01/2018\n02/28/2019\nApply",
    ]);
});

test("scales attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="month,day,trololo"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(columnHeaders).toHaveLength(32);

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Day",
        "Month",
        "12/01/2018\n02/28/2019\nApply",
    ]);
});

test("precision attribute ('day': 'hour:quarter')", async () => {
    onRpc("write", ({ args }) => expect.step(args));
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'day': 'hour:quarter'}"
            />
        `,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
        domain: [["id", "=", 7]],
    });

    // resize of a quarter
    const dropHandle = await resizePill(getPillWrapper("Task 7"), "end", 0.25, false);
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveText("1:30 PM");
    expect(SELECTORS.stopBadge).toHaveText("7:44 PM (+15 minutes)");

    // manually trigger the drop to trigger a write
    await dropHandle();
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveCount(0);
    expect(SELECTORS.stopBadge).toHaveCount(0);
    expect.verifySteps([[[7], { stop: "2018-12-20 18:44:59" }]]);

    const { moveTo, drop } = await dragPill("Task 7");
    await moveTo({ columnHeader: "12pm", groupHeader: "Thursday, December 20, 2018", part: 4 });
    expect(SELECTORS.startBadge).toHaveText("12:45 PM");
    expect(SELECTORS.stopBadge).toHaveText("6:59 PM");
    expect(SELECTORS.startBadge).toHaveClass("text-danger");
    expect(SELECTORS.stopBadge).toHaveClass("text-danger");
    await drop();
    expect.verifySteps([[[7], { start: "2018-12-20 11:45:12", stop: "2018-12-20 17:59:59" }]]);
});

test("precision attribute ('month': 'day:full')", async () => {
    onRpc("write", ({ args }) => expect.step(args));
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt
                date_start="start"
                date_stop="stop"
                precision="{'month': 'day:full'}"
            />
        `,
        domain: [["id", "=", 7]],
    });

    // resize of a quarter
    const dropHandle = await resizePill(getPillWrapper("Task 7"), "end", 2, false);
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveText("12/20/2018");
    expect(SELECTORS.stopBadge).toHaveText("12/22/2018 (+48 hours)");

    // manually trigger the drop to trigger a write
    await dropHandle();
    await animationFrame();
    expect(SELECTORS.startBadge).toHaveCount(0);
    expect(SELECTORS.stopBadge).toHaveCount(0);
    expect.verifySteps([[[7], { stop: "2018-12-22 18:29:59" }]]);

    const { moveTo, drop } = await dragPill("Task 7");
    await moveTo({ columnHeader: "23", groupHeader: "December 2018" });
    expect(SELECTORS.startBadge).toHaveText("12/23/2018");
    expect(SELECTORS.stopBadge).toHaveText("12/25/2018");
    expect(SELECTORS.startBadge).toHaveClass("text-success");
    expect(SELECTORS.stopBadge).toHaveClass("text-success");
    await drop();
    expect.verifySteps([[[7], { start: "2018-12-23 12:30:12", stop: "2018-12-25 18:29:59" }]]);
});

test("progress attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" progress="progress"/>`,
        groupBy: ["project_id"],
    });
    expect(`${SELECTORS.pill} .o_gantt_progress`).toHaveCount(3);
    expect(
        queryAll(SELECTORS.pill).map((el) => ({
            text: el.innerText,
            progress: el.querySelector(".o_gantt_progress")?.style?.width || null,
        }))
    ).toEqual([
        { text: "Task 1", progress: null },
        { text: "Task 2", progress: "30%" },
        { text: "Task 4", progress: null },
        { text: "Task 3", progress: "60%" },
        { text: "Task 7", progress: "80%" },
    ]);
});

test("form_view_id attribute", async () => {
    Tasks._views[["form", 42]] = `<form><field name="name"/></form>`;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" form_view_id="42"/>`,
        groupBy: ["project_id"],
    });
    onRpc("get_views", ({ kwargs }) => expect.step(["get_views", kwargs.views]));
    await contains(queryFirst(SELECTORS.addButton + ":visible")).click();
    expect(".modal .o_form_view").toHaveCount(1);
    expect.verifySteps([
        ["get_views", [[42, "form"]]], // get_views when form view dialog opens
    ]);
});

test("decoration attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `
            <gantt date_start="start" date_stop="stop" decoration-info="stage == 'todo'">
                <field name="stage"/>
            '</gantt>
        `,
    });
    expect(getPill("Task 1")).toHaveClass("decoration-info");
    expect(getPill("Task 2")).not.toHaveClass("decoration-info");
});

test("decoration attribute with date", async () => {
    mockDate("2018-12-19T12:00:00");
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" decoration-danger="start &lt; today"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("decoration-danger");
    expect(getPill("Task 2")).toHaveClass("decoration-danger");
    expect(getPill("Task 5")).toHaveClass("decoration-danger");
    expect(getPill("Task 3")).not.toHaveClass("decoration-danger");
    expect(getPill("Task 4")).not.toHaveClass("decoration-danger");
    expect(getPill("Task 7")).not.toHaveClass("decoration-danger");
});

test("color attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="color"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("o_gantt_color_0");
    expect(getPill("Task 2")).toHaveClass("o_gantt_color_2");
});

test("color attribute in multi-level grouped", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="color"/>`,
        groupBy: ["user_id", "project_id"],
        domain: [["id", "=", 1]],
    });
    expect(`${SELECTORS.pill}.o_gantt_consolidated_pill`).not.toHaveClass("o_gantt_color_0");
    expect(`${SELECTORS.pill}:not(.o_gantt_consolidated_pill)`).toHaveClass("o_gantt_color_0");
});

test("color attribute on a many2one", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" color="project_id"/>`,
    });
    expect(getPill("Task 1")).toHaveClass("o_gantt_color_1");
    expect(`${SELECTORS.pill}.o_gantt_color_1`).toHaveCount(4);
    expect(`${SELECTORS.pill}.o_gantt_color_2`).toHaveCount(2);
});

test(`Today style with unavailabilities ("week": "day:half")`, async () => {
    const unavailabilities = [
        {
            start: "2018-12-18 10:00:00",
            stop: "2018-12-20 14:00:00",
        },
    ];

    onRpc("get_gantt_data", ({ parent }) => {
        const result = parent();
        result.unavailabilities.__default = { false: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
    });

    // Normal day / unavailability
    expect(getCellColorProperties("Tuesday 18", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);

    // Full unavailability
    expect(getCellColorProperties("Wednesday 19", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);

    // Unavailability / today
    expect(getCell("Thursday 20", "Week 51, Dec 16 - Dec 22")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("Thursday 20", "Week 51, Dec 16 - Dec 22")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOffToday-background-color",
    ]);
});

test("Today style of group rows", async () => {
    const unavailabilities = [
        {
            start: "2018-12-18 10:00:00",
            stop: "2018-12-20 14:00:00",
        },
    ];
    Tasks._records = [Tasks._records[3]]; // id: 4

    onRpc("get_gantt_data", ({ parent }) => {
        expect.step("get_gantt_data");
        const result = parent();
        result.unavailabilities.project_id = { 1: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
        groupBy: ["user_id", "project_id"],
    });
    expect.verifySteps(["get_gantt_data"]);
    await contains(".o_gantt_header_folded").click();

    // Normal group cell: open
    let cell4 = getCell("Wednesday 19", "Week 51, Dec 16 - Dec 22", "User 1");
    expect(cell4).not.toHaveClass("o_gantt_today");
    expect(cell4).toHaveClass("o_group_open");
    expect(cell4).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(248, 249, 250), rgb(233, 236, 239))",
    });

    // Today group cell: open
    let cell5 = getCell("Thursday 20", "Week 51, Dec 16 - Dec 22", "User 1");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).toHaveClass("o_group_open");
    expect(cell5).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(248, 249, 250), rgb(233, 236, 239))",
    });
    await contains(`${SELECTORS.rowHeader}${SELECTORS.group}:eq(1)`).click(); // fold group ("User 1", after the "Undefined Assign To" group)
    await leave();
    // Normal group cell: closed
    cell4 = getCell("Wednesday 19", "Week 51, Dec 16 - Dec 22", "User 1");
    expect(cell4).not.toHaveClass("o_gantt_today");
    expect(cell4).not.toHaveClass("o_group_open");
    expect(cell4).toHaveStyle({
        backgroundImage: "linear-gradient(rgb(233, 236, 239), rgb(248, 249, 250))",
    });

    // Today group cell: closed
    cell5 = getCell("Thursday 20", "Week 51, Dec 16 - Dec 22", "User 1");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).not.toHaveClass("o_group_open");
    expect(cell5).toHaveStyle({ backgroundImage: "none" });
    expect(cell5).toHaveStyle({ backgroundColor: "rgb(252, 250, 243)" });
});

test("style without unavailabilities", async () => {
    mockDate("2018-12-05T02:00:00");

    onRpc("get_gantt_data", ({ kwargs }) => {
        expect.step("get_gantt_data");
        expect(kwargs.unavailability_fields).toEqual([]);
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    const cell5 = getCell("05", "December 2018");
    expect(cell5).toHaveClass("o_gantt_today");
    expect(cell5).toHaveAttribute("style", "grid-area: r1 / c9 / r5 / c11;");
    const cell6 = getCell("06", "December 2018");
    expect(cell6).toHaveAttribute("style", "grid-area: r1 / c11 / r5 / c13;");
});

test(`Unavailabilities ("month": "day:half")`, async () => {
    mockDate("2018-12-05T02:00:00");

    const unavailabilities = [
        {
            start: "2018-12-05 09:30:00",
            stop: "2018-12-07 08:00:00",
        },
        {
            start: "2018-12-16 09:00:00",
            stop: "2018-12-18 13:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ model, kwargs, parent }) => {
        expect.step("get_gantt_data");
        expect(model).toBe("tasks");
        expect(kwargs.unavailability_fields).toEqual([]);
        expect(kwargs.start_date).toBe("2018-11-30 23:00:00");
        expect(kwargs.stop_date).toBe("2019-02-28 23:00:00");
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1"/>`,
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(getCell("05", "December 2018")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("05", "December 2018")).toEqual([
        "--Gantt__DayOffToday-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("06", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("07", "December 2018")).toEqual([]);
    expect(getCellColorProperties("16", "December 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("17", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("18", "December 2018")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
    ]);
});

test(`Unavailabilities ("day": "hours:quarter")`, async () => {
    Tasks._records = [];
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-19 08:15:00",
            stop: "2018-12-19 08:30:00",
        },
        {
            start: "2018-12-19 10:35:00",
            stop: "2018-12-19 12:29:00",
        },
        {
            start: "2018-12-19 20:15:00",
            stop: "2018-12-19 20:50:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    expect(getCellColorProperties("9am", "Wednesday, December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
    ]);
    expect(getCellColorProperties("11am", "Wednesday, December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("12pm", "Wednesday, December 19, 2018")).toEqual([
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCellColorProperties("1pm", "Wednesday, December 19, 2018")).toEqual([
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
        "--Gantt__Day-background-color",
    ]);
    expect(getCellColorProperties("9pm", "Wednesday, December 19, 2018")).toEqual([
        "--Gantt__Day-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__DayOff-background-color",
        "--Gantt__Day-background-color",
    ]);
});

test(`Fold unavailabilities ("day": "hours:quarter")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-19 07:00:00",
        },
        {
            start: "2018-12-19 11:00:00",
            stop: "2018-12-19 12:25:00",
        },
        {
            start: "2018-12-19 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
        {
            start: "2018-12-20 16:15:00",
            stop: "2018-12-22 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" scales="day" default_range="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(28);
    expect(groupHeaders).toEqual(
        [
            {
                range: [1, 97],
                title: "Wednesday, December 19, 2018",
                titleAttr: "Wednesday, December 19, 2018",
            },
            {
                range: [97, 193],
                title: "Thursday, December 20, 2018",
                titleAttr: "Thursday, December 20, 2018",
            },
            {
                range: [193, 289],
                title: "",
                titleAttr: "",
            },
        ],
        { message: "Last group's title is hidden since all of its content is folded" }
    );
    expect(columnHeaders).toEqual([
        { range: [1, 33], title: "", titleAttr: "" },
        { range: [33, 37], title: "8am", titleAttr: "Wednesday, December 19, 2018, 8:00 AM" },
        { range: [37, 41], title: "9am", titleAttr: "Wednesday, December 19, 2018, 9:00 AM" },
        { range: [41, 45], title: "10am", titleAttr: "Wednesday, December 19, 2018, 10:00 AM" },
        { range: [45, 49], title: "11am", titleAttr: "Wednesday, December 19, 2018, 11:00 AM" },
        { range: [49, 53], title: "12pm", titleAttr: "Wednesday, December 19, 2018, 12:00 PM" },
        { range: [53, 57], title: "1pm", titleAttr: "Wednesday, December 19, 2018, 1:00 PM" },
        { range: [57, 61], title: "2pm", titleAttr: "Wednesday, December 19, 2018, 2:00 PM" },
        { range: [61, 65], title: "3pm", titleAttr: "Wednesday, December 19, 2018, 3:00 PM" },
        { range: [65, 69], title: "4pm", titleAttr: "Wednesday, December 19, 2018, 4:00 PM" },
        { range: [69, 73], title: "5pm", titleAttr: "Wednesday, December 19, 2018, 5:00 PM" },
        { range: [73, 109], title: "", titleAttr: "" },
        { range: [109, 113], title: "3am", titleAttr: "Thursday, December 20, 2018, 3:00 AM" },
        { range: [113, 117], title: "4am", titleAttr: "Thursday, December 20, 2018, 4:00 AM" },
        { range: [117, 121], title: "5am", titleAttr: "Thursday, December 20, 2018, 5:00 AM" },
        { range: [121, 125], title: "6am", titleAttr: "Thursday, December 20, 2018, 6:00 AM" },
        { range: [125, 129], title: "7am", titleAttr: "Thursday, December 20, 2018, 7:00 AM" },
        { range: [129, 133], title: "8am", titleAttr: "Thursday, December 20, 2018, 8:00 AM" },
        { range: [133, 137], title: "9am", titleAttr: "Thursday, December 20, 2018, 9:00 AM" },
        { range: [137, 141], title: "10am", titleAttr: "Thursday, December 20, 2018, 10:00 AM" },
        { range: [141, 145], title: "11am", titleAttr: "Thursday, December 20, 2018, 11:00 AM" },
        { range: [145, 149], title: "12pm", titleAttr: "Thursday, December 20, 2018, 12:00 PM" },
        { range: [149, 153], title: "1pm", titleAttr: "Thursday, December 20, 2018, 1:00 PM" },
        { range: [153, 157], title: "2pm", titleAttr: "Thursday, December 20, 2018, 2:00 PM" },
        { range: [157, 161], title: "3pm", titleAttr: "Thursday, December 20, 2018, 3:00 PM" },
        { range: [161, 165], title: "4pm", titleAttr: "Thursday, December 20, 2018, 4:00 PM" },
        { range: [165, 169], title: "5pm", titleAttr: "Thursday, December 20, 2018, 5:00 PM" },
        { range: [169, 289], title: "", titleAttr: "" },
    ]);
    expect(".o_gantt_header_cell [data-icon='arrow_left']:visible").toHaveCount(3);
    expect(queryFirst(".o_gantt_cell").offsetWidth).toBe(36, {
        message: "Folded cells have a fixed width of 36px",
    });
});

test(`Fold unavailabilities ("week": "day:half")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-14 16:00:00",
            stop: "2018-12-17 07:00:00",
        },
        {
            start: "2018-12-18 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
    });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(11);
    expect(groupHeaders).toEqual([
        {
            range: [1, 15],
            title: "Week 50, Dec 9 - Dec 15",
            titleAttr: "Week 50, Dec 9 - Dec 15",
        },
        {
            range: [15, 29],
            title: "Week 51, Dec 16 - Dec 22",
            titleAttr: "Week 51, Dec 16 - Dec 22",
        },
        {
            range: [29, 43],
            title: "Week 52, Dec 23 - Dec 29",
            titleAttr: "Week 52, Dec 23 - Dec 29",
        },
    ]);
    expect(columnHeaders).toEqual([
        { range: [9, 11], title: "Thursday 13", titleAttr: "Thursday, December 13, 2018" },
        { range: [11, 13], title: "Friday 14", titleAttr: "Friday, December 14, 2018" },
        { range: [13, 17], title: "", titleAttr: "" },
        { range: [17, 19], title: "Monday 17", titleAttr: "Monday, December 17, 2018" },
        { range: [19, 21], title: "Tuesday 18", titleAttr: "Tuesday, December 18, 2018" },
        { range: [21, 23], title: "", titleAttr: "" }, // Single unavailability columns are folded in week scale
        { range: [23, 25], title: "Thursday 20", titleAttr: "Thursday, December 20, 2018" },
        { range: [25, 27], title: "Friday 21", titleAttr: "Friday, December 21, 2018" },
        { range: [27, 29], title: "Saturday 22", titleAttr: "Saturday, December 22, 2018" },
        { range: [29, 31], title: "Sunday 23", titleAttr: "Sunday, December 23, 2018" },
        { range: [31, 33], title: "Monday 24", titleAttr: "Monday, December 24, 2018" },
    ]);
    expect(".o_gantt_header_cell [data-icon='arrow_left']:visible").toHaveCount(2);
});

test(`Fold unavailabilities when grouped, with records in the "Undefined" row`, async () => {
    Tasks._records = [
        { ...Tasks._records[3], resource_ids: [1] }, // id: 4
        { ...Tasks._records[6], resource_ids: [] }, // id: 7, lands in the "Undefined Resources" row
    ];
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-14 16:00:00",
            stop: "2018-12-17 07:00:00",
        },
        {
            start: "2018-12-18 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ parent }) => {
        const result = parent();
        result.unavailabilities.resource_ids = { 1: unavailabilities };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="week" scales="week" precision="{'week': 'day:half'}"/>`,
        groupBy: ["resource_ids"],
    });
    const { columnHeaders, rows } = getGridContent();
    expect(rows.map((r) => r.title)).toEqual(["Undefined Resources", "Resource 1"]);
    // The "Undefined Resources" row has no unavailability of its own: it must
    // not prevent the columns unavailable for every real resource from folding.
    expect(columnHeaders.map((c) => c.title)).toEqual([
        "Thursday 13",
        "Friday 14",
        "",
        "Monday 17",
        "Tuesday 18",
        "",
        "Thursday 20",
        "Friday 21",
        "Saturday 22",
        "Sunday 23",
        "Monday 24",
    ]);
    expect(".o_gantt_header_cell [data-icon='arrow_left']:visible").toHaveCount(2);
});

test(`Fold unavailabilities ("month": "day:half")`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-11-13 16:00:00",
            stop: "2018-11-16 07:00:00",
        },
        {
            start: "2018-11-19 16:15:00",
            stop: "2018-11-29 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="month" scales="month" precision="{'month': 'day:half'}"/>`,
    });
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    const { columnHeaders, groupHeaders } = getGridContent({ setTitleAttrOnHeaders: true });
    expect(columnHeaders).toHaveLength(30);
    expect(groupHeaders).toEqual([
        {
            range: [1, 61],
            title: "November 2018",
            titleAttr: "November 2018",
        },
        {
            range: [61, 123],
            title: "December 2018",
            titleAttr: "December 2018",
        },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 3], title: "01", titleAttr: "Thursday, November 1, 2018" },
        { range: [3, 5], title: "02", titleAttr: "Friday, November 2, 2018" },
        { range: [5, 7], title: "03", titleAttr: "Saturday, November 3, 2018" },
        { range: [7, 9], title: "04", titleAttr: "Sunday, November 4, 2018" },
        { range: [9, 11], title: "05", titleAttr: "Monday, November 5, 2018" },
        { range: [11, 13], title: "06", titleAttr: "Tuesday, November 6, 2018" },
        { range: [13, 15], title: "07", titleAttr: "Wednesday, November 7, 2018" },
        { range: [15, 17], title: "08", titleAttr: "Thursday, November 8, 2018" },
        { range: [17, 19], title: "09", titleAttr: "Friday, November 9, 2018" },
        { range: [19, 21], title: "10", titleAttr: "Saturday, November 10, 2018" },
        { range: [21, 23], title: "11", titleAttr: "Sunday, November 11, 2018" },
        { range: [23, 25], title: "12", titleAttr: "Monday, November 12, 2018" },
        { range: [25, 27], title: "13", titleAttr: "Tuesday, November 13, 2018" },
        { range: [27, 31], title: "", titleAttr: "" },
        { range: [31, 33], title: "16", titleAttr: "Friday, November 16, 2018" },
        { range: [33, 35], title: "17", titleAttr: "Saturday, November 17, 2018" },
        { range: [35, 37], title: "18", titleAttr: "Sunday, November 18, 2018" },
        { range: [37, 39], title: "19", titleAttr: "Monday, November 19, 2018" },
        { range: [39, 57], title: "", titleAttr: "" },
        { range: [57, 59], title: "29", titleAttr: "Thursday, November 29, 2018" },
        { range: [59, 61], title: "30", titleAttr: "Friday, November 30, 2018" },
        { range: [61, 63], title: "01", titleAttr: "Saturday, December 1, 2018" },
        { range: [63, 65], title: "02", titleAttr: "Sunday, December 2, 2018" },
        { range: [65, 67], title: "03", titleAttr: "Monday, December 3, 2018" },
        { range: [67, 69], title: "04", titleAttr: "Tuesday, December 4, 2018" },
        { range: [69, 71], title: "05", titleAttr: "Wednesday, December 5, 2018" },
        { range: [71, 73], title: "06", titleAttr: "Thursday, December 6, 2018" },
        { range: [73, 75], title: "07", titleAttr: "Friday, December 7, 2018" },
        { range: [75, 77], title: "08", titleAttr: "Saturday, December 8, 2018" },
        { range: [77, 79], title: "09", titleAttr: "Sunday, December 9, 2018" },
    ]);
    expect(".o_gantt_header_cell [data-icon='arrow_left']:visible").toHaveCount(2);
    const cell1 = queryFirst(".o_gantt_cell");
    const cell2 = queryOne(".o_gantt_cell:eq(1)");
    expect(Math.abs(cell1.clientWidth - cell2.clientWidth)).toBeLessThan(4, {
        message:
            "Folded cells have similar width compared to regular cells besides covering a wider date range",
    });
});

test(`Fold unavailabilities with multiple rows`, async () => {
    const unavailabilities1 = [
        // in utc
        { start: "2018-12-18 16:00:00", stop: "2018-12-19 07:00:00" },
        { start: "2018-12-19 11:00:00", stop: "2018-12-19 12:25:00" },
        { start: "2018-12-19 16:15:00", stop: "2018-12-20 08:00:00" },
        { start: "2018-12-20 16:15:00", stop: "2018-12-22 08:00:00" },
    ];
    const unavailabilities2 = [
        // in utc
        { start: "2018-12-18 16:00:00", stop: "2018-12-19 09:00:00" },
        { start: "2018-12-19 13:15:00", stop: "2018-12-20 08:00:00" },
        { start: "2018-12-20 20:15:00", stop: "2018-12-22 08:00:00" },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual(["user_id"]);
        const result = parent();
        result.unavailabilities = { user_id: { 1: unavailabilities1, 2: unavailabilities2 } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
        groupBy: ["user_id"],
        domain: [["id", "in", [4, 7]]],
    });
    const { columnHeaders, groupHeaders } = getGridContent();
    expect(groupHeaders).toEqual([
        { range: [1, 97], title: "Wednesday, December 19, 2018" },
        { range: [97, 193], title: "Thursday, December 20, 2018" },
        { range: [193, 289], title: "" },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 33], title: "" },
        { range: [33, 37], title: "8am" },
        { range: [37, 41], title: "9am" },
        { range: [41, 45], title: "10am" },
        { range: [45, 49], title: "11am" },
        { range: [49, 53], title: "12pm" },
        { range: [53, 57], title: "1pm" },
        { range: [57, 61], title: "2pm" },
        { range: [61, 65], title: "3pm" },
        { range: [65, 69], title: "4pm" },
        { range: [69, 73], title: "5pm" },
        { range: [73, 109], title: "" },
        { range: [109, 113], title: "3am" },
        { range: [113, 117], title: "4am" },
        { range: [117, 121], title: "5am" },
        { range: [121, 125], title: "6am" },
        { range: [125, 129], title: "7am" },
        { range: [129, 133], title: "8am" },
        { range: [133, 137], title: "9am" },
        { range: [137, 141], title: "10am" },
        { range: [141, 145], title: "11am" },
        { range: [145, 149], title: "12pm" },
        { range: [149, 153], title: "1pm" },
        { range: [153, 157], title: "2pm" },
        { range: [157, 161], title: "3pm" },
        { range: [161, 165], title: "4pm" },
        { range: [165, 169], title: "5pm" },
        { range: [169, 173], title: "6pm" },
        { range: [173, 177], title: "7pm" },
        { range: [177, 181], title: "8pm" },
        { range: [181, 185], title: "9pm" },
        { range: [185, 289], title: "" },
    ]);
});

test(`Partial fold/unfold in gantt`, async () => {
    Tasks._records = [Tasks._records[3]]; // id: 4
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-19 07:00:00",
        },
        {
            start: "2018-12-19 11:00:00",
            stop: "2018-12-19 12:25:00",
        },
        {
            start: "2018-12-19 16:15:00",
            stop: "2018-12-20 08:00:00",
        },
        {
            start: "2018-12-20 16:15:00",
            stop: "2018-12-22 08:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    setCellParts(4);
    await contains(".o_gantt_scroll_container").scroll({ left: 0 });
    let { columnHeaders, rows } = getGridContent();
    expect(columnHeaders).toHaveLength(28);
    expect(columnHeaders[11]).toEqual({
        range: [73, 109],
        title: "",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "3am (2/4) Thursday, December 20, 2018 -> 7am (2/4) Thursday, December 20, 2018",
        level: 0,
    });
    await contains(".o_gantt_cell:eq(11)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(36);
    expect(columnHeaders[11]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    await runAllTimers();
    await contains(".o_gantt_cell:eq(0)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(38);
    expect(columnHeaders[11]).toEqual({
        range: [45, 49],
        title: "11am",
    });
    expect(columnHeaders[18]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    await contains(".o_gantt_header_cell:eq(18)").hover();
    expect(".o_gantt_header_cell:eq(19)").toHaveClass("o_gantt_foldable_hovered");
    await contains(".o_gantt_header_cell:eq(18)").click();
    ({ columnHeaders } = getGridContent());
    expect(columnHeaders).toHaveLength(35);
    expect(columnHeaders[18]).toEqual({
        range: [73, 109],
        title: "",
    });
    const { drop } = await dragPill("Task 4");
    await drop({ columnHeader: "5pm", groupHeader: "Wednesday, December 19, 2018", part: 4 });
    ({ columnHeaders, rows } = getGridContent());
    expect(columnHeaders).toHaveLength(39);
    expect(columnHeaders[18]).toEqual({
        range: [73, 77],
        title: "6pm",
    });
    expect(columnHeaders[22]).toEqual({
        range: [89, 109],
        title: "",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "5pm (3/4) Wednesday, December 19, 2018 -> 9pm (3/4) Wednesday, December 19, 2018",
        level: 0,
    });
    await resizePill(getPillWrapper("Task 4"), "end", +1); // wrong but we don't want to rewrite helpers for this
    ({ columnHeaders, rows } = getGridContent());
    expect(columnHeaders).toHaveLength(39);
    expect(columnHeaders[22]).toEqual({
        range: [89, 93],
        title: "10pm",
    });
    expect(rows[0].pills[0]).toEqual({
        title: "Task 4",
        colSpan: "5pm (3/4) Wednesday, December 19, 2018 -> 3am Thursday, December 20, 2018",
        level: 0,
    });
});

test(`Full unavailabilities period`, async () => {
    Tasks._records = []; // no pill
    const unavailabilities = [
        // in utc
        {
            start: "2018-12-18 16:00:00",
            stop: "2018-12-23 07:00:00",
        },
    ];
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        expect(kwargs.unavailability_fields).toEqual([]);
        const result = parent();
        result.unavailabilities = { __default: { false: unavailabilities } };
        return result;
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" display_unavailability="1" default_range="day" scales="day" precision="{'day': 'hours:quarter'}"/>`,
    });
    // Only one folded cell appears which takes the full screen width instead of 36px
    expect(SELECTORS.cell).toHaveCount(1);
    expect(SELECTORS.cell).toHaveClass("o_gantt_cell_folded");
    expect(SELECTORS.cell).toHaveRect({ width: 1366 });
    expect(SELECTORS.groupHeader).toHaveCount(2);
    expect(queryAllTexts(SELECTORS.groupHeader)).toEqual(["", ""]);

    await contains(SELECTORS.cell).click();
    const { columnHeaders, groupHeaders } = getGridContent();
    expect(groupHeaders).toEqual([
        { range: [1, 97], title: "Wednesday, December 19, 2018" },
        { range: [97, 193], title: "Thursday, December 20, 2018" },
    ]);
    expect(columnHeaders).toEqual([
        { range: [1, 5], title: "12am" },
        { range: [5, 9], title: "1am" },
        { range: [9, 13], title: "2am" },
        { range: [13, 17], title: "3am" },
        { range: [17, 21], title: "4am" },
        { range: [21, 25], title: "5am" },
        { range: [25, 29], title: "6am" },
        { range: [29, 33], title: "7am" },
        { range: [33, 37], title: "8am" },
        { range: [37, 41], title: "9am" },
        { range: [41, 45], title: "10am" },
        { range: [45, 49], title: "11am" },
        { range: [49, 53], title: "12pm" },
        { range: [53, 57], title: "1pm" },
        { range: [57, 61], title: "2pm" },
        { range: [61, 65], title: "3pm" },
        { range: [65, 69], title: "4pm" },
        { range: [69, 73], title: "5pm" },
        { range: [73, 77], title: "6pm" },
        { range: [77, 81], title: "7pm" },
        { range: [81, 85], title: "8pm" },
        { range: [85, 89], title: "9pm" },
        { range: [89, 93], title: "10pm" },
        { range: [93, 97], title: "11pm" },
        { range: [97, 101], title: "12am" },
        { range: [101, 105], title: "1am" },
        { range: [105, 109], title: "2am" },
        { range: [109, 113], title: "3am" },
        { range: [113, 117], title: "4am" },
        { range: [117, 121], title: "5am" },
        { range: [121, 125], title: "6am" },
        { range: [125, 129], title: "7am" },
        { range: [129, 133], title: "8am" },
        { range: [133, 137], title: "9am" },
        { range: [137, 141], title: "10am" },
        { range: [141, 145], title: "11am" },
        { range: [145, 149], title: "12pm" },
        { range: [149, 153], title: "1pm" },
    ]);
});

test("default_group_by attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>`,
    });

    expect(`.o_searchview_facet`).toHaveCount(1);
    expect(`.o_searchview_facet`).toHaveText("Assign To");
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            title: "Undefined Assign To",
        },
        {
            title: "User 1",
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 1,
                    title: "Task 1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                    title: "Task 4",
                },
            ],
        },
        {
            title: "User 2",
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "Task 2",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 1,
                    title: "Task 7",
                },
                {
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                    title: "Task 3",
                },
            ],
        },
    ]);
});

test("default_group_by attribute with groupBy", async () => {
    // The default_group_by attribute should be ignored if a groupBy is given.
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id"/>`,
        groupBy: ["project_id"],
    });

    expect(`.o_searchview_facet`).toHaveCount(0);
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 0,
                    title: "Task 1",
                },
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
                {
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 1,
                    title: "Task 3",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 7",
                },
            ],
        },
    ]);
});

test("default_group_by attribute with 2 fields", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_group_by="user_id,project_id"/>`,
    });

    expect(`.o_searchview_facet`).toHaveCount(1);
    expect(`.o_searchview_facet`).toHaveText("Assign To\n>\nProject");
    const { rows } = getGridContent();
    expect(rows).toEqual([
        {
            isGroup: true,
            title: "Undefined Assign To",
        },
        {
            title: "Undefined Project",
        },
        {
            title: "User 1",
            isGroup: true,
            pills: [
                {
                    colSpan: "Out of bounds (8)  -> 19 December 2018",
                    title: "1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    title: "2",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 31 December 2018",
                    title: "1",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "Out of bounds (1)  -> 31 December 2018",
                    level: 0,
                    title: "Task 1",
                },
                {
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                    title: "Task 4",
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
                {
                    colSpan: "17 (1/2) December 2018 -> 20 (1/2) December 2018",
                    title: "1",
                },
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    title: "2",
                },
                {
                    colSpan: "21 December 2018 -> 22 (1/2) December 2018",
                    title: "1",
                },
                {
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    title: "1",
                },
            ],
        },
        {
            title: "Project 1",
            pills: [
                {
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                    title: "Task 2",
                },
                {
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                    title: "Task 3",
                },
            ],
        },
        {
            title: "Project 2",
            pills: [
                {
                    colSpan: "20 (1/2) December 2018 -> 20 December 2018",
                    level: 0,
                    title: "Task 7",
                },
            ],
        },
    ]);
});

test("default_range attribute", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" default_range="day"/>`,
    });
    const { columnHeaders, range } = getGridContent();
    expect(range).toBe("Day");
    expect(columnHeaders).toHaveLength(42);
    await click(SELECTORS.scaleSelectorToggler);
    await animationFrame();
    const firstRangeMenuItem = queryFirst(`${SELECTORS.scaleSelectorMenu} .dropdown-item`);
    expect(firstRangeMenuItem).toHaveClass("active");
    expect(firstRangeMenuItem).toHaveText("Day");
});

test("default_range not in scales", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" scales="month" default_range="year"/>`,
    });
    const { range } = getGridContent();
    expect(range).toBe("Year");

    await contains(SELECTORS.scaleSelectorToggler).click();
    await animationFrame();
    expect(`${SELECTORS.scaleSelectorMenu} .dropdown-item`).toHaveCount(3);
    expect(queryAllTexts(`${SELECTORS.scaleSelectorMenu} .dropdown-item`)).toEqual([
        "Month",
        "Year",
        "01/01/2017\n12/31/2019\nApply",
    ]);
});

test("verifies context-driven text visibility in card", async () => {
    Tasks._views["card,23"] = `
        <card>
            <templates>
                <t t-name="card">
                    Allocated Hours: <field name="allocated_hours"/>
                    <div invisible="context.get('isProjectNameHidden')">Project A</div>
                    <div invisible="context.get('isTaskNameHidden')">Test 5</div>
                </t>
            </templates>
        </card>
    `;

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop"><popover card_id="23"/></gantt>`,
        context: { isTaskNameHidden: true, isProjectNameHidden: false },
    });
    await contains(SELECTORS.pill).click();
    await runAllTimers();
    await waitFor(`.o_popover`);
    expect(`.o_popover .o_popover_body`).toHaveText("Allocated Hours:\n0.00\nProject A");
});

test("side panel to schedule", async () => {
    Tasks._records[0].start = false;
    Tasks._records[0].stop = false;
    onRpc(({ method }) => {
        expect.step(method);
    });
    onRpc("write", ({ args, kwargs }) => {
        expect(args).toEqual([
            [1],
            {
                project_id: 1,
                start: "2018-12-13 23:00:00",
                stop: "2018-12-14 23:00:00",
            },
        ]);
        expect(kwargs.context.from_custom_context).toBe(true);
    });
    onRpc("web_search_read", ({ kwargs }) => {
        expect(kwargs.domain).toEqual(["&", ["start", "=", false], ["stop", "=", false]]);
        expect(kwargs.limit).toBe(20);
        expect(kwargs.specification).toEqual({ display_name: {} });
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
        context: { from_custom_context: true },
    });
    let { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(33);
    expect(rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                },
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
    ]);
    expect(SELECTORS.sidePanel).toHaveCount(1);
    expect(SELECTORS.sidePanel).toHaveText("1 to schedule\nTask 1");
    expect.verifySteps(["get_views", "get_gantt_data", "web_search_read"]);
    const { moveTo, drop } = await dragToSchedule("Task 1");
    await moveTo({ columnHeader: "14", groupHeader: "December 2018", row: "Project 1" });
    expect(SELECTORS.startBadge).toHaveText("12/14/2018, 12:00 AM");
    expect(SELECTORS.stopBadge).toHaveText("12/15/2018, 12:00 AM");
    await drop();
    expect.verifySteps(["write", "get_gantt_data", "web_search_read"]);
    ({ range, viewTitle, columnHeaders, rows } = getGridContent());
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(33);
    expect(rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 1",
                    colSpan: "14 December 2018 -> 14 December 2018",
                    level: 0,
                },
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                },
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
    ]);
    expect(SELECTORS.sidePanel).toHaveText("Nothing to schedule");
});

test("side panel: event can be dragged and scheduled by its name", async () => {
    Tasks._records[0].start = false;
    Tasks._records[0].stop = false;

    onRpc("write", ({ args }) => {
        expect.step("write");
        expect(args[0]).toEqual([1]);
    });

    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
    });

    expect(SELECTORS.sidePanel).toHaveText("1 to schedule\nTask 1");

    // Drag by clicking the event NAME (span).
    const nameEl = queryFirst(`${SELECTORS.eventToSchedule}:contains(Task 1) span`);
    const dragActions = await contains(nameEl).drag();
    const cell = await hoverGridCell("14", "December 2018", "Project 1");
    await dragActions.moveTo(cell, { position: { x: 1 }, relative: true });
    await dragActions.drop();

    expect.verifySteps(["write"]);
    expect(SELECTORS.sidePanel).toHaveText("Nothing to schedule");
});

test("side panel to unschedule", async () => {
    Tasks._records[0].start = false;
    Tasks._records[0].stop = false;
    onRpc(({ method }) => {
        expect.step(method);
    });
    onRpc("write", ({ args, kwargs }) => {
        expect(args).toEqual([
            [2],
            {
                start: false,
                stop: false,
            },
        ]);
        expect(kwargs.context.from_custom_context).toBe(true);
    });
    onRpc("web_search_read", ({ kwargs }) => {
        expect(kwargs.domain).toEqual(["&", ["start", "=", false], ["stop", "=", false]]);
        expect(kwargs.limit).toBe(20);
        expect(kwargs.specification).toEqual({ display_name: {} });
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
        context: { from_custom_context: true },
    });
    let { range, viewTitle, columnHeaders, rows } = getGridContent();
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(33);
    expect(rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 2",
                    colSpan: "17 (1/2) December 2018 -> 22 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 1,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                },
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
    ]);
    expect(SELECTORS.sidePanel).toHaveCount(1);
    expect(SELECTORS.sidePanel).toHaveText("1 to schedule\nTask 1");
    expect.verifySteps(["get_views", "get_gantt_data", "web_search_read"]);
    const { moveTo, drop } = await dragPill("Task 2");
    await animationFrame();
    expect(SELECTORS.unscheduleZone).toHaveCount(1);
    expect(SELECTORS.unscheduleZone).toHaveText("Drop here to unschedule");
    await moveTo({ unschedule: true });
    await drop();
    expect.verifySteps(["write", "get_gantt_data", "web_search_read"]);
    ({ range, viewTitle, columnHeaders, rows } = getGridContent());
    expect(range).toBe("12/01/2018 -> 02/28/2019");
    expect(viewTitle).toBe("Tasks");
    expect(columnHeaders).toHaveLength(33);
    expect(rows).toEqual([
        {
            title: "Undefined Project",
        },
        {
            title: "Project 1",
            pills: [
                {
                    title: "Task 4",
                    colSpan: "20 December 2018 -> 20 (1/2) December 2018",
                    level: 0,
                },
                {
                    title: "Task 3",
                    colSpan: "27 December 2018 -> 03 (1/2) January 2019",
                    level: 0,
                },
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
    ]);
    expect(SELECTORS.sidePanel).toHaveText("2 to schedule\nTask 1\nTask 2");
});

test("gantt sidepanel can be collapsed/expanded", async () => {
    patchWithCleanup(localStorage, {
        setItem(key, value) {
            if (key.startsWith("gantt_sidepanel_expanded")) {
                expect.step(["setItem", key, value]);
            }
            super.setItem(...arguments);
        },
    });
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
    });
    expect(SELECTORS.sidePanel).toHaveText("Nothing to schedule");
    expect(SELECTORS.sidePanel).toHaveCount(1);
    await contains(SELECTORS.sideBarToggler).click();
    expect(SELECTORS.sidePanel).toHaveCount(0);
    expect(SELECTORS.sideBarController).toHaveText("Nothing to schedule");
    expect.verifySteps([["setItem", "gantt_sidepanel_expanded,-1,false", false]]);
    await contains(SELECTORS.sideBarToggler).click();
    expect(SELECTORS.sidePanel).toHaveText("Nothing to schedule");
    expect(SELECTORS.sidePanel).toHaveCount(1);
    expect.verifySteps([["setItem", "gantt_sidepanel_expanded,-1,false", true]]);
});

test("gantt sidepanel can be collapsed by default if it was set in local storage beforehand", async () => {
    localStorage.setItem("gantt_sidepanel_expanded,-1,false", false);
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
    });
    expect(SELECTORS.sidePanel).toHaveCount(0);
    expect(SELECTORS.sideBarController).toHaveText("Nothing to schedule");
});

test("gantt sidepanel can be resized", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["project_id"],
    });
    const sidePanel = queryFirst(SELECTORS.sidePanel);
    const resizeHandle = queryFirst(".o_gantt_sidepanel_resize");
    const originalWidth = sidePanel.offsetWidth;

    const { drop } = await drag(resizeHandle);
    await drop(resizeHandle, { position: { x: 500 } });
    expect(sidePanel.offsetWidth).toBeGreaterThan(originalWidth);
});

test("edge scrolling is disabled while side panel is expanded", async () => {
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
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1"/>`,
        groupBy: ["user_id", "project_id", "stage"],
    });
    await scroll(".o_gantt_scroll_container", { left: 300 });
    let pill = getPillWrapper("Task 2");
    await hoverPillCell(pill);
    await dragAndExpect(pill, { x: 0 }, () => {
        expect(".o_gantt_scroll_container").toHaveProperty("scrollLeft", 300, {
            message: "Should have stayed still because side panel is expanded",
        });
    });
    await contains(SELECTORS.sideBarToggler).click();
    pill = getPillWrapper("Task 2");
    await hoverPillCell(pill);
    await dragAndExpect(pill, { x: 0 }, () => {
        expect(".o_gantt_scroll_container").toHaveProperty("scrollLeft", 0, {
            message: "Should have reached 0 since side panel is collapsed",
        });
    });
});

test("gantt side panel hidden by default in sample mode", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" schedule="1" sample="1"/>`,
        groupBy: ["project_id"],
        domain: Domain.FALSE.toList(),
    });
    expect(".o_view_nocontent").toHaveCount(1);
    expect(SELECTORS.sidePanel).toHaveCount(0, {
        message: "The side panel should be hidden in sample mode",
    });
});

test("buffer attributes", async () => {
    Tasks._records[1].buffer_start = 40.0;
    Tasks._records[1].buffer_stop = 8.0;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" buffer_start="buffer_start" buffer_stop="buffer_stop"/>`,
        groupBy: ["project_id"],
    });
    expect(getPillWrapper("Task 2")).toHaveStyle({ gridColumn: "c34 / c44", gridRow: "r4 / r5" });
    expect(getPillBuffer("Task 2")).toHaveStyle({ gridColumn: "c31 / c45", gridRow: "r4 / r5" });
});

test("pill buffers disappear on pill drag/resize", async () => {
    Tasks._records[1].buffer_start = 40.0;
    Tasks._records[1].buffer_stop = 8.0;
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt string="Tasks" date_start="start" date_stop="stop" buffer_start="buffer_start" buffer_stop="buffer_stop"/>`,
        groupBy: ["project_id"],
    });
    const pillBuffer = getPillBuffer("Task 2");
    expect(pillBuffer).toBeVisible();
    const { moveTo, drop } = await dragPill("Task 2");
    await moveTo({ columnHeader: "16", groupHeader: "December 2018" });
    expect(pillBuffer).not.toBeVisible();
    await drop();
    expect(getPillBuffer("Task 2")).toBeVisible();
    const dropHandle = await resizePill(getPillWrapper("Task 2"), "end", 2, false);
    expect(getPillBuffer("Task 2")).not.toBeVisible();
    await dropHandle();
    expect(getPillBuffer("Task 2")).toBeVisible();
});
