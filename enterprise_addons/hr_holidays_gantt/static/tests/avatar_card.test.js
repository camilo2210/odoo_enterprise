import { beforeEach, describe, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";
import { mountView } from "@web/../tests/web_test_helpers";
import { defineHrHolidaysGanttModels } from "@hr_holidays_gantt/../tests/hr_holidays_gantt_test_helpers";

describe.current.tags("desktop");

defineHrHolidaysGanttModels();

function createPublicEmployee(pyEnv, name, avatar_leave_summary) {
    const employeeId = pyEnv["hr.employee"].create({
        name,
        avatar_leave_summary,
    });

    pyEnv["hr.employee.public"].create({
        name,
        employee_id: employeeId,
    });
    
    return employeeId;
}

let pyEnv;
let pierreId;
let paulId;

beforeEach(async () => {
    mockDate("2025-01-01 00:00:00", +0);
    pyEnv = await startServer();
    
    pierreId = createPublicEmployee(pyEnv, "Pierre", [
        {
            display_name: "Paid Time Off",
            unit: "days",
            leaves_taken: 5,
            remaining_leaves: 15,
            max_leaves: 20,
            requires_allocation: true,
        },
    ]);

    paulId = createPublicEmployee(pyEnv, "Paul", []);

    pyEnv["hr.leave"].create([
        {
            display_name: "Pierre's Leave",
            employee_id: pierreId,
            date_from: "2025-01-01 00:00:00",
            date_to: "2025-01-02 00:00:00",
            state: "confirm",
        },
        {
            display_name: "Paul's Leave",
            employee_id: paulId,
            date_from: "2025-01-01 00:00:00",
            date_to: "2025-01-02 00:00:00",
            state: "confirm",
        },
    ]);
});

test("avatar card shows leave summary when employee has time off", async () => {
    await start();

    await mountGanttView({
        resModel: "hr.leave",
    });

    await contains(".o_gantt_row_header img", { count: 2 });
    await click(".o_gantt_row_header:contains('Pierre') img");
    
    await contains(".o_avatar_card");
    await contains(".o_avatar_card .o_avatar_card_leave_summary");
    await contains(".o_avatar_card .o_avatar_card_leave_summary .d-flex.small", {
        text: "Paid Time Off: 5 days /15 days",
    });
});

test("avatar card does not show leave summary when employee has no time off", async () => {
    await start();

    await mountGanttView({
        resModel: "hr.leave",
    });

    await contains(".o_gantt_row_header img", { count: 2 });
    await click(".o_gantt_row_header:contains('Paul') img");
    
    await contains(".o_avatar_card");
    await contains(".o_avatar_card .o_avatar_card_leave_summary", { count: 1 });
});

test("avatar card does not show leave summary in a standard Kanban view", async () => {
    pyEnv["m2o.avatar.employee"].create({ employee_id: pierreId });

    await start();

    await mountView({
        type: "kanban",
        resModel: "m2o.avatar.employee",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="employee_id" widget="many2one_avatar_employee"/>
                    </t>
                </templates>
            </kanban>
        `,
    });

    await contains(".o_m2o_avatar img", { count: 1 });
    await click(".o_m2o_avatar img");

    await contains(".o_avatar_card");
    await contains(".o_avatar_card .o_avatar_card_leave_summary", { count: 0 });
});
