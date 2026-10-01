import { patchUiSize, SIZES } from "@mail/../tests/mail_test_helpers";
import { expect } from "@odoo/hoot";
import { fields, models, onRpc } from "@web/../tests/web_test_helpers";
import { mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";

export class Attendances extends models.Model {
    name = fields.Char();
    check_in = fields.Datetime({ string: "Start Date" });
    check_out = fields.Datetime({ string: "Stop Date" });
    employee_id = fields.Many2one({
        string: "Attendance Of",
        relation: "employees",
        required: true,
    });

    _records = [
        {
            id: 1,
            check_in: "2018-12-10 09:00:00",
            check_out: "2018-12-10 12:00:00",
            name: "Attendance 1",
            employee_id: 1,
        },
        {
            id: 2,
            check_in: "2018-12-10 13:00:00",
            check_out: false,
            name: "Attendance 2",
            employee_id: 1,
        },
        {
            id: 3,
            check_in: "2018-12-10 08:00:00",
            check_out: "2018-12-10 16:00:00",
            name: "Attendance 3",
            employee_id: 2,
        },
    ];
}

export class Employees extends models.Model {
    name = fields.Char();

    _records = [
        { id: 1, name: "Employee 1" },
        { id: 2, name: "Employee 2" },
    ];
}

/**
 * Mounts the attendance gantt view with a mocked `get_gantt_data` rpc returning
 * the given progress bar values. `progressBars` should have the same format as
 * the return value of `_gantt_progress_bar()`.
 */
export async function mountGanttViewWithProgressBars(progressBars) {
    // to make sure that the "value / max (extra)" label is not shortened
    patchUiSize({ size: SIZES.XXL });

    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        const result = parent();
        expect(kwargs.progress_bar_fields).toEqual(["employee_id"]);
        result.progress_bars.employee_id = progressBars;
        return result;
    });

    await mountGanttView({
        resModel: "attendances",
        arch: `
            <gantt
                js_class="attendance_gantt"
                date_start="check_in"
                date_stop="check_out"
                default_group_by="employee_id"
                progress_bar="employee_id">
                <field name="employee_id"/>
            </gantt>`,
        context: {
            default_start_date: "2018-12-10",
            default_stop_date: "2018-12-10",
        },
    });
}
