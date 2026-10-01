import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate, advanceTime, runAllTimers } from "@odoo/hoot-mock";
import { defineModels, defineParams, onRpc, contains } from "@web/../tests/web_test_helpers";
import {
    getCell,
    getGridContent,
    mountGanttView,
    SELECTORS,
} from "@web_gantt/../tests/web_gantt_test_helpers";
import {
    Attendances,
    Employees,
    mountGanttViewWithProgressBars,
} from "@hr_attendance_gantt/../tests/attendance_gantt_test_helpers";

describe.current.tags("desktop");

defineMailModels();
defineModels([Attendances, Employees]);

beforeEach(() => {
    defineParams({
        lang_parameters: {
            time_format: "%I:%M:%S",
        },
    });
});

test("Open Ended record today", async () => {
    mockDate("2018-12-10 16:00:00", +0);
    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-10",
            default_stop_date: "2018-12-10",
        },
    });
    const { range, rows } = getGridContent();
    expect(range).toBe("12/10/2018 -> 12/10/2018");
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "9am Monday, December 10, 2018 -> 11am Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 1",
                },
                {
                    colSpan: "1pm Monday, December 10, 2018 -> 4pm Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 2",
                },
            ],
            title: "Employee 1",
        },
        {
            pills: [
                {
                    colSpan: "8am Monday, December 10, 2018 -> 3pm Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 3",
                },
            ],
            title: "Employee 2",
        },
    ]);
});

test("Future Open Ended record not displayed", async () => {
    mockDate("2018-12-10 12:00:00", +0);
    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-10",
            default_stop_date: "2018-12-10",
        },
    });
    const { range, rows } = getGridContent();
    expect(range).toBe("12/10/2018 -> 12/10/2018");
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "9am Monday, December 10, 2018 -> 11am Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 1",
                },
            ],
            title: "Employee 1",
        },
        {
            pills: [
                {
                    colSpan: "8am Monday, December 10, 2018 -> 3pm Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 3",
                },
            ],
            title: "Employee 2",
        },
    ]);
});

test("Open Ended record spanning multiple days", async () => {
    mockDate("2018-12-12 14:00:00", +0);
    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-12",
            default_stop_date: "2018-12-12",
        },
    });
    let gridContent = getGridContent();
    expect(gridContent.range).toBe("12/12/2018 -> 12/12/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "12am Wednesday, December 12, 2018 -> 2pm Wednesday, December 12, 2018",
                    level: 0,
                    title: "Attendance 2",
                },
            ],
            title: "Employee 1",
        },
    ]);
    await click(queryOne(SELECTORS.previousButton));
    await advanceTime(500);
    await animationFrame();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("12/11/2018 -> 12/11/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "12am Tuesday, December 11, 2018 -> 11pm Tuesday, December 11, 2018",
                    level: 0,
                    title: "Attendance 2",
                },
            ],
            title: "Employee 1",
        },
    ]);
    await click(queryOne(SELECTORS.previousButton));
    await advanceTime(500);
    await animationFrame();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("12/10/2018 -> 12/10/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "9am Monday, December 10, 2018 -> 11am Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 1",
                },
                {
                    colSpan: "1pm Monday, December 10, 2018 -> 11pm Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 2",
                },
            ],
            title: "Employee 1",
        },
        {
            pills: [
                {
                    colSpan: "8am Monday, December 10, 2018 -> 3pm Monday, December 10, 2018",
                    level: 0,
                    title: "Attendance 3",
                },
            ],
            title: "Employee 2",
        },
    ]);
});

test("Concurrent open-ended records", async () => {
    mockDate("2018-12-20 15:00:00", +0);
    Attendances._records = [
        {
            id: 4,
            check_in: "2018-12-20 08:00:00",
            check_out: false,
            name: "Attendance 4",
            employee_id: 1,
        },
        {
            id: 5,
            check_in: "2018-12-20 09:00:00",
            check_out: false,
            name: "Attendance 5",
            employee_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
    });
    const { range, rows } = getGridContent();
    expect(range).toBe("12/20/2018 -> 12/20/2018");
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "8am Thursday, December 20, 2018 -> 3pm Thursday, December 20, 2018",
                    level: 0,
                    title: "Attendance 4",
                },
                {
                    colSpan: "9am Thursday, December 20, 2018 -> 3pm Thursday, December 20, 2018",
                    level: 1,
                    title: "Attendance 5",
                },
            ],
            title: "Employee 1",
        },
    ]);
});

test("Open ended record Precision", async () => {
    mockDate("2018-12-20 15:35:00", +0);
    Attendances._records = [
        {
            id: 4,
            check_in: "2018-12-20 08:00:00",
            check_out: false,
            name: "Attendance 4",
            employee_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" precision="{'day': 'hour:quarter'}" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
    });
    const { range, rows } = getGridContent();
    expect(range).toBe("12/20/2018 -> 12/20/2018");
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "8am Thursday, December 20, 2018 -> 3pm (3/4) Thursday, December 20, 2018",
                    level: 0,
                    title: "Attendance 4",
                },
            ],
            title: "Employee 1",
        },
    ]);
});

test("Open ended record updated correctly", async () => {
    mockDate("2018-12-20 14:00:00", +0);
    Attendances._records = [
        {
            id: 4,
            check_in: "2018-12-20 08:00:00",
            check_out: false,
            name: "Attendance 4",
            employee_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-12-20",
            default_stop_date: "2018-12-20",
        },
    });
    let gridContent = getGridContent();
    expect(gridContent.range).toBe("12/20/2018 -> 12/20/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "8am Thursday, December 20, 2018 -> 2pm Thursday, December 20, 2018",
                    level: 0,
                    title: "Attendance 4",
                },
            ],
            title: "Employee 1",
        },
    ]);
    mockDate("2018-12-20 18:00:00", +0);
    await click(queryOne(SELECTORS.previousButton));
    await advanceTime(500);
    await animationFrame();
    await click(queryOne(SELECTORS.nextButton));
    await advanceTime(500);
    await animationFrame();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("12/20/2018 -> 12/20/2018");
    // TODO fixme: end hour is non deterministic and alternates between 7pm and 8pm.
    const endHour = parseInt(gridContent.rows[0].pills[0].colSpan.match(/->\s*(\d+)/)[1]);
    expect(endHour).toBeWithin(6, 7);
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: `8am Thursday, December 20, 2018 -> ${endHour}pm Thursday, December 20, 2018`,
                    level: 0,
                    title: "Attendance 4",
                },
            ],
            title: "Employee 1",
        },
    ]);
});

test("Future Open ended record not shown before it happens and appears after start date.", async () => {
    mockDate("2018-11-02 12:00:00", +0);
    Attendances._records = [
        {
            id: 5,
            check_in: "2018-11-02 09:00:00",
            check_out: "2018-11-02 12:00:00",
            name: "Attendance 5",
            employee_id: 1,
        },
        {
            id: 6,
            check_in: "2018-11-02 14:00:00",
            check_out: false,
            name: "Attendance 6",
            employee_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        context: {
            default_start_date: "2018-11-02",
            default_stop_date: "2018-11-02",
        },
    });
    let gridContent = getGridContent();
    expect(gridContent.range).toBe("11/02/2018 -> 11/02/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "9am Friday, November 2, 2018 -> 11am Friday, November 2, 2018",
                    level: 0,
                    title: "Attendance 5",
                },
            ],
            title: "Employee 1",
        },
    ]);
    mockDate("2018-11-02 17:00:00", +0);
    await click(queryOne(SELECTORS.previousButton));
    await advanceTime(500);
    await animationFrame();
    await click(queryOne(SELECTORS.nextButton));
    await advanceTime(500);
    await animationFrame();
    gridContent = getGridContent();
    expect(gridContent.range).toBe("11/02/2018 -> 11/02/2018");
    expect(gridContent.rows).toEqual([
        {
            pills: [
                {
                    colSpan: "9am Friday, November 2, 2018 -> 11am Friday, November 2, 2018",
                    level: 0,
                    title: "Attendance 5",
                },
                {
                    colSpan: "2pm Friday, November 2, 2018 -> 5pm Friday, November 2, 2018",
                    level: 0,
                    title: "Attendance 6",
                },
            ],
            title: "Employee 1",
        },
    ]);
});

test("Domain correctly applied when allow_open_ended=1.", async () => {
    mockDate("2018-11-02 19:00:00", +0);
    Attendances._records = [
        {
            id: 7,
            check_in: "2018-11-02 15:00:00",
            check_out: "2018-11-02 19:00:00",
            name: "Attendance 7",
            employee_id: 2,
        },
        {
            id: 8,
            check_in: "2018-11-02 14:00:00",
            check_out: false,
            name: "Attendance 8",
            employee_id: 1,
        },
        {
            id: 9,
            check_in: "2018-11-02 08:00:00",
            check_out: "2018-11-02 14:00:00",
            name: "Attendance 9",
            employee_id: 1,
        },
    ];

    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' date_stop="check_out"/>`,
        domain: ["|", ["employee_id", "=", 2], ["check_out", "=", false]],
        context: {
            default_start_date: "2018-11-02",
            default_stop_date: "2018-11-02",
        },
    });
    const { rows, range } = getGridContent();
    expect(range).toBe("11/02/2018 -> 11/02/2018");
    expect(rows).toEqual([
        {
            pills: [
                {
                    colSpan: "2pm Friday, November 2, 2018 -> 7pm Friday, November 2, 2018",
                    level: 0,
                    title: "Attendance 8",
                },
            ],
            title: "Employee 1",
        },
        {
            pills: [
                {
                    colSpan: "3pm Friday, November 2, 2018 -> 6pm Friday, November 2, 2018",
                    level: 0,
                    title: "Attendance 7",
                },
            ],
            title: "Employee 2",
        },
    ]);
});

test("Dragging half column in week scale preserves checkout context", async () => {
    expect.assertions(2);
    mockDate("2025-08-01 14:00:00", +0);
    Attendances._views = {
        form: `
            <form>
                <field name="name"/>
                <field name="check_in"/>
                <field name="check_out"/>
                <field name="employee_id"/>
            </form>
        `,
    };
    onRpc("onchange", ({ kwargs }) => {
        expect(kwargs.context.check_out).not.toBeEmpty();
        expect(kwargs.context.default_check_out).not.toBeEmpty();
    });
    await mountGanttView({
        resModel: "attendances",
        arch: `<gantt js_class="attendance_gantt" date_start="check_in" default_group_by='employee_id' default_scale="week" date_stop="check_out" plan="false"/>`,
        context: {
            default_start_date: "2025-08-01",
            default_stop_date: "2025-08-07",
        },
    });
    const { moveTo, drop } = await contains(getCell("Friday 1", "Week 31, Jul 27 - Aug 2")).drag();
    await moveTo(getCell("Friday 1", "Week 31, Jul 27 - Aug 2"));
    await runAllTimers(); // Pointer move is subjected to throttleForAnimation in gantt
    await drop();
    await animationFrame();
});

test("Progress bar shown with correct label and color", async () => {
    mockDate("2018-12-10 16:00:00", +0);
    await mountGanttViewWithProgressBars({
        1: { value: 6, max_value: 8 },
        2: { value: 10, max_value: 8 },
    });

    // both employees should have their progress bar shown.
    expect(SELECTORS.progressBar).toHaveCount(2);

    const [pb1, pb2] = queryAll(SELECTORS.progressBar);
    // below max, text color should be normal
    expect(pb1.querySelector("span")).not.toHaveClass("bg-warning");
    // overtime, should show as warning/orange
    expect(pb2.querySelector("span")).toHaveClass("bg-warning");

    // check that progress bars are filled corectly
    expect(queryAll(SELECTORS.progressBarBackground).map((el) => el.style.width)).toEqual([
        "75%",
        "100%",
    ]);

    // below max shows "X left", overtime shows "+Y"
    const [label1, label2] = queryAll(SELECTORS.progressBarForeground);
    expect(label1.textContent).toInclude("6h / 8h");
    expect(label1.textContent).toInclude("2h left");
    expect(label2.textContent).toInclude("10h / 8h");
    expect(label2.textContent).toInclude("+2h");

    // a progress bar label that is at success status should not be colored
    expect(label1).not.toHaveClass("text-warning");
    expect(label1).not.toHaveClass("text-success");

    // when there is overtime, the label is colored in orange (warning)
    expect(label2).toHaveClass("text-warning");
});

test("Progress bar shown for employees without attendances", async () => {
    mockDate("2018-12-10 16:00:00", +0);
    await mountGanttViewWithProgressBars({
        // employee with no attendances at all
        1: { value: 0, max_value: 8 },
        2: { value: 4, max_value: 8 },
    });

    // the progress bar must be shown but empty
    expect(SELECTORS.progressBar).toHaveCount(2);
    const [emptyBar] = queryAll(SELECTORS.progressBar);
    expect(emptyBar.querySelector("span").style.width).toBe("0%");

    // an empty employee is not considered a warning. It stays at "success"
    // (i.e. no color)
    const [emptyLabel] = queryAll(SELECTORS.progressBarForeground);
    expect(emptyLabel.textContent).toEqual("0h / 8h");
    expect(emptyLabel).not.toHaveClass("text-warning");
});
