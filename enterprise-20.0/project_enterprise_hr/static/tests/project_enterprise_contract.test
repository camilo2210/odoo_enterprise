import { expect, test, beforeEach, describe } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";

import { mountView, onRpc, makeMockServer } from "@web/../tests/web_test_helpers";
import { unfoldAllColumns } from "@web_gantt/../tests/web_gantt_test_helpers";

import { defineProjectEnterpriseHrModels } from "./project_enterprise_hr_contract_models";

describe.current.tags("desktop");
defineProjectEnterpriseHrModels();

let userId = false;
let versionId = false;
let partnerId = false;
let env;

beforeEach(async () => {
    mockDate("2024-03-27", +0);
    const mockServer = await makeMockServer();
    env = mockServer.env;

    partnerId = env["res.partner"].create({ name: "Pig-1" });
    userId = env["res.users"].create({ partner_id: partnerId });

    env["project.task"].create({
        name: "Task-1",
        project_id: 1,
        display_in_project: true,
        user_ids: [userId],
        planned_date_begin: "2024-03-27 09:00:00",
        date_deadline: "2024-03-27 18:00:00",
    });

    const employeeId = env["hr.employee"].create({
        user_id: userId,
        name: "Pig-1",
    });

    env["res.users"].write(userId, {
        employee_id: employeeId,
    });

    versionId = env["hr.version"].create({
        name: "Contract - Pig",
        employee_id: employeeId,
        contract_date_start: "2024-03-28 00:00:00",
        contract_date_end: "2024-03-28 23:50:59",
    });
});

const ganttViewParams = {
    resModel: "project.task",
    type: "gantt",
    arch: `
        <gantt js_class="task_gantt" date_start="planned_date_begin" date_stop="date_deadline" default_group_by="user_ids"
        display_unavailability="1">
        </gantt>
    `,
    context: {
        default_start_date: "2024-03-24",
        default_stop_date: "2024-03-30",
    },
};

onRpc("get_gantt_data", ({ parent, kwargs }) => {
    const result = parent();
    result.unavailabilities = {
        user_ids: {
            [userId]: [
                { start: "2024-03-23 18:00:00", stop: "2024-03-25 09:00:00" },
                { start: "2024-03-28 18:00:00", stop: "2024-04-01 09:00:00" },
            ],
            false: [
                { start: "2024-03-23 18:00:00", stop: "2024-03-25 09:00:00" },
                { start: "2024-03-28 18:00:00", stop: "2024-04-01 09:00:00" },
            ],
        },
    };

    if (kwargs.groupby.includes("user_ids")) {
        const userIds = new Set();
        for (const group of result.groups) {
            const resId = group.user_ids ? group.user_ids[0] : false;
            if (resId) {
                userIds.add(resId)
            }
        }

        const employeeIds = new Set();
        for (const user of env["res.users"].browse([...userIds])) {
            if (!user.employee_id) {
                continue;
            }
            const employee_id = user.employee_id;
            employeeIds.add(employee_id);
        }
        result.working_periods = env["hr.employee"]._get_working_periods_by_field(employeeIds, kwargs.start_date, kwargs.stop_date, "user_id");;
    }
    return result;
});

/*
    The following cases are to be checked/tested.
╔══════════╦══════════╦══════════════════╦══════════════════════════════════════════════════════╗
║ Employee ║ Contract ║ Status           ║ Behaviour                                            ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 1        ║ No       ║ None             ║ White it in working days and grey according          ║
║          ║          ║                  ║ to the user calendar                                 ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 2        ║ Yes      ║ Running          ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the user calendar, and grey everywhere outside       ║
║          ║          ║                  ║ of the contract period                               ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 3        ║ Yes      ║ Expired          ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the user calendar, and grey everywhere outside       ║
║          ║          ║                  ║ of the contract period                               ║
╠══════════╬══════════╬══════════════════╬══════════════════════════════════════════════════════╣
║ 4        ║ Yes      ║ Cancelled        ║ White & grey during the contract period according to ║
║          ║          ║                  ║ the user calendar, and grey everywhere outside       ║
║          ║          ║                  ║ of the contract period                               ║
╚══════════╩══════════╩══════════════════╩══════════════════════════════════════════════════════╝
*/
test("check gantt shading for user without contract (case-1)", async () => {
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']").toHaveCount(3);
    expect(".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff'])").toHaveCount(4);
});

test("check gantt shading for user with a running contract contract (case-2)", async () => {
    env["hr.version"].write(versionId, {
        contract_date_start: "2024-03-27 00:00:00",
        contract_date_end: "2024-03-30 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_user_has_no_working_periods").toHaveCount(3);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_user_has_no_working_periods)"
    ).toHaveCount(2);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_user_has_no_working_periods)"
    ).toHaveCount(2);
});

test("check gantt shading for user with a expired contract (case-3)", async () => {
    env["hr.version"].write(versionId, {
        contract_date_start: "2024-03-20 00:00:00",
        contract_date_end: "2024-03-25 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_user_has_no_working_periods").toHaveCount(5);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_user_has_no_working_periods)"
    ).toHaveCount(1);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_user_has_no_working_periods)"
    ).toHaveCount(1);
});

test("check gantt shading for user with a cancelled contract (case-4)", async () => {
    env["hr.version"].write(versionId, {
        active: false,
        contract_date_start: "2024-03-27 00:00:00",
        contract_date_end: "2024-03-30 23:59:59",
    });
    await mountView(ganttViewParams);
    await unfoldAllColumns();
    expect(".o_user_has_no_working_periods").toHaveCount(0);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1'][style*='Gantt__DayOff']:not(.o_user_has_no_working_periods)"
    ).toHaveCount(3);
    expect(
        ".o_gantt_cell[data-row-id*='Pig-1']:not([style*='Gantt__DayOff']):not(.o_user_has_no_working_periods)"
    ).toHaveCount(4);
});
