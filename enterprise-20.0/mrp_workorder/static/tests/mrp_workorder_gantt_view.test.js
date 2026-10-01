import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { defineModels, fields, models, onRpc } from "@web/../tests/web_test_helpers";
import {
    getCell,
    getCellColorProperties,
    mountGanttView,
} from "@web_gantt/../tests/web_gantt_test_helpers";

describe.current.tags("desktop");

class Workorder extends models.Model {
    name = fields.Char();
    date_start = fields.Datetime();
    date_finished = fields.Datetime();
    workcenter_id = fields.Many2one({
        string: "Work Center",
        relation: "workcenter",
        required: true,
    });

    _records = [
        {
            id: 1,
            name: "Blop",
            date_start: "2023-02-24 08:00:00",
            date_finished: "2023-03-20 08:00:00",
            workcenter_id: 1,
        },
        {
            id: 2,
            name: "Yop",
            date_start: "2023-02-22 08:00:00",
            date_finished: "2023-03-27 08:00:00",
            workcenter_id: 2,
        },
    ];

    _views = {
        form: `
            <form>
                <field name="name"/>
                <field name="start_datetime"/>
                <field name="date_deadline"/>
            </form>
        `,
    };
}

class Workcenter extends models.Model {
    name = fields.Char();

    _records = [
        { id: 1, name: "Assembly Line 1" },
        { id: 2, name: "Assembly Line 2" },
    ];
}

defineMailModels();
defineModels([Workorder, Workcenter]);

test("unavailabilities fetched for workcenter_id (in groupBy)", async () => {
    mockDate("2023-03-05 07:00:00");
    onRpc("get_gantt_data", ({ parent, kwargs }) => {
        const result = parent();
        expect.step("get_gantt_data");
        expect(kwargs.unavailability_fields).toEqual(["workcenter_id"]);
        result.unavailabilities.workcenter_id = {
            1: [{ start: "2023-03-05 07:00:00", stop: "2023-03-06 07:00:00" }],
        };
        return result;
    });
    await mountGanttView({
        resModel: "workorder",
        arch: `
            <gantt js_class="mrp_workorder_gantt" date_start="date_start" date_stop="date_finished" display_unavailability="1">
                <field name="workcenter_id" />
            </gantt>
        `,
        groupBy: ["workcenter_id"],
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(getCell("05", "March 2023")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("05", "March 2023")).toEqual([
        "--Gantt__DayOffToday-background-color",
        "--Gantt__DayOff-background-color",
    ]);
    expect(getCell("05", "March 2023", "Assembly line 2")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("05", "March 2023", "Assembly line 2")).toEqual([]);
});

test("unavailabilities fetched for workcenter_id  (not in groupBy)", async () => {
    mockDate("2023-03-05 07:00:00");
    Workorder._fields.other_workcenter_id = fields.Many2one({
        string: "Other Work Center",
        relation: "workcenter",
    });
    Workorder._records[0].other_workcenter_id = 1;
    onRpc("get_gantt_data", ({ parent, kwargs }) => {
        const result = parent();
        expect.step("get_gantt_data");
        expect(kwargs.unavailability_fields).toEqual([]);
        result.unavailabilities.workcenter_id = {
            1: [{ start: "2023-03-05 07:00:00", stop: "2023-03-06 07:00:00" }],
        };
        return result;
    });
    await mountGanttView({
        resModel: "workorder",
        arch: `
            <gantt js_class="mrp_workorder_gantt" date_start="date_start" date_stop="date_finished">
                <field name="workcenter_id" />
            </gantt>
        `,
        groupBy: ["other_workcenter_id"],
    });
    expect.verifySteps(["get_gantt_data"]);
    expect(getCell("05", "March 2023")).toHaveClass("o_gantt_today");
    expect(getCellColorProperties("05", "March 2023")).toEqual([]);
});

test("test total planned time per day", async () => {
    Workorder._records = [
        {
            id: 1,
            name: "Blop",
            date_start: "2023-03-06 08:00:00",
            date_finished: "2023-03-06 09:42:00",
            workcenter_id: 1,
        },
    ];
    mockDate("2023-03-05 07:00:00");

    await mountGanttView({
        arch: `
            <gantt
                js_class="mrp_workorder_gantt"
                date_start="date_start"
                date_stop="date_finished"
                total_row="1"
            />
        `,
        resModel: "workorder",
        groupBy: ["workcenter_id"],
    });
    expect(".o_gantt_row_total .o_gantt_pill").toHaveText("1h 42m");
});
