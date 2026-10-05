/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryAllTexts, waitFor } from "@odoo/hoot-dom";
import { SELECTORS, hoverGridCell, mountGanttView } from "@web_gantt/../tests/web_gantt_test_helpers";
import { advanceTime, animationFrame, mockDate } from "@odoo/hoot-mock";
import { contains, makeMockServer, mountView, onRpc } from "@web/../tests/web_test_helpers";
import { startServer } from "@mail/../tests/mail_test_helpers";
import { defineHrHolidaysGanttModels } from "@hr_holidays_gantt/../tests/hr_holidays_gantt_test_helpers";
import { HrHolidaysGanttLeave } from "@hr_holidays_gantt/../tests/mock_server/mock_models/hr_leave";

describe.current.tags("desktop");
defineHrHolidaysGanttModels();

beforeEach(() => {
    mockDate("2025-01-01 12:00:00", +0);
    HrHolidaysGanttLeave._records = [];
});

test("Model displays correct quick add buttons for the available leave types", async () => {
    const pyEnv = await startServer();

    const employeeId = pyEnv["hr.employee"].create({
        name: "Test Employee",
    });

    pyEnv["hr.leave"].create({
        display_name: "Leave",
        employee_id: employeeId,
        date_from: "2025-01-01 00:00:00",
        date_to: "2025-01-02 00:00:00",
        state: "confirm",
        work_entry_type_id: 55,
    });

    let leaveTypeFetchCount = 0;
    onRpc(({ model, method }) => {
        if (model === "hr.employee" && method === "get_employee_available_leave_types") {
            leaveTypeFetchCount++;
            return [
                {
                    id: 65,
                    sequence: 1,
                    name: "Unpaid Leave",
                    color: 1,
                    display_code: "UL",
                    requires_allocation: false,
                },
                {
                    id: 55,
                    sequence: 2,
                    name: "Paid Leave",
                    color: 2,
                    display_code: "PL",
                    requires_allocation: true,
                    remaining_leaves: 4,
                    allocated_leaves: 10,
                    unit: "days",
                },
            ];
        }
    });

    await mountGanttView({ resModel: "hr.leave" });

    await click(".o_gantt_cell");
    await animationFrame();

    expect(leaveTypeFetchCount).toBe(1);

    expect(".o_multi_selection_buttons").toHaveCount(1);
    expect(".o_multi_selection_buttons .btn:contains(Apply)").toHaveCount(1);
    expect(".o_multi_selection_buttons .btn[data-tooltip='Delete']").toHaveCount(1);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn").toHaveCount(2);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn[data-tooltip='Add Unpaid Leave']").toHaveCount(1);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn[data-tooltip='Add Paid Leave']").toHaveCount(1);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn:contains(UL)").toHaveCount(1);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn:contains(PL)").toHaveCount(1);
    expect(".o_multi_selection_buttons .o_hr_holidays_gantt_quick_add_btn:contains(4 days left)").toHaveCount(1);

    const button_pannel = document.body.querySelector(".o_multi_selection_buttons")
    expect(button_pannel.querySelectorAll(".o_hr_holidays_gantt_quick_add_btn")[0].dataset.tooltip).toBe("Add Unpaid Leave");
    expect(button_pannel.querySelectorAll(".o_hr_holidays_gantt_quick_add_btn")[1].dataset.tooltip).toBe("Add Paid Leave");
});

describe("time off popover", () => {
    const FOOTER = ".o_work_entry_popover .popover-footer";
    const EDIT_BTN = `${FOOTER} button:has([data-icon='edit'])`;
    const APPROVE_BTN = `${FOOTER} button:has([data-icon='thumb_up'])`;
    const SAVE_BTN = `${FOOTER} button:has([data-icon='save'])`;
    const DISCARD_BTN = `${FOOTER} button:contains(Discard)`;
    const DELETE_BTN = `${FOOTER} button:has([data-icon='delete'].oi-filled)`;
    const NAME_INPUT = ".o_work_entry_popover .o_field_widget[name='name'] input";

    function createLeave(env, values = {}) {
        const [employeeId] = env["hr.employee"].create([{ name: "Employee 1", active: true }]);
        const [typeId] = env["hr.work.entry.type"].create([{ name: "Paid Time Off" }]);
        const [leaveId] = env["hr.leave"].create([
            {
                name: "Time off",
                employee_id: employeeId,
                work_entry_type_id: typeId,
                date_from: "2025-01-06 08:00:00",
                date_to: "2025-01-08 17:00:00",
                state: "validate",
                can_back_to_approve: true,
                ...values,
            },
        ]);
        return leaveId;
    }

    async function openLeavePopover() {
        await click(SELECTORS.pill);
        // double-click debounced
        await advanceTime(200);
        await waitFor(`${FOOTER} button`);
    }

    test("Edit switches the read-only popover to edit mode", async () => {
        const { env } = await makeMockServer();
        createLeave(env); // approved time off -> opens read-only
        onRpc("action_back_to_approval", () => true);
        await mountView({ type: "gantt", resModel: "hr.leave" });
        await openLeavePopover();

        // read-only: the description cannot be edited
        expect(NAME_INPUT).toHaveCount(0);

        // Edit -> the popover is no longer read-only
        await click(EDIT_BTN);
        await waitFor(NAME_INPUT);
        expect(NAME_INPUT).toHaveCount(1);
    });

    test("editing a field offers Discard, and approving saves it", async () => {
        const { env } = await makeMockServer();
        // editable, by a reader who may act on it
        const leaveId = createLeave(env, {
            state: "confirm",
            can_approve: true,
            can_refuse: true,
        });
        onRpc("web_save", function ({ parent }) {
            expect.step("web_save");
            return parent();
        });
        onRpc("action_approve", () => {
            expect.step("action_approve");
            return true;
        });
        await mountView({ type: "gantt", resModel: "hr.leave" });
        await openLeavePopover();

        // editable, but nothing to discard yet
        expect(NAME_INPUT).toHaveCount(1);
        expect(DISCARD_BTN).toHaveCount(0);
        expect(DELETE_BTN).toHaveCount(1);

        // a dirty record offers Discard, and Approve/Refuse carry the pending edit
        await contains(NAME_INPUT).edit("Updated time off");
        await waitFor(DISCARD_BTN);
        expect(queryAllTexts(`${FOOTER} button`)).toEqual(["Approve", "Refuse", "Discard"]);

        // approving saves the pending edit first
        await click(APPROVE_BTN);
        await waitFor(DELETE_BTN);
        expect.verifySteps(["web_save", "action_approve"]);
        expect(DISCARD_BTN).toHaveCount(0);
        const [leave] = env["hr.leave"].read(leaveId, ["name"]);
        expect(leave.name).toBe("Updated time off");
    });

    test("a reader who may not approve saves on its own", async () => {
        const { env } = await makeMockServer();
        const leaveId = createLeave(env, { state: "confirm" }); // editable, no rights
        onRpc("web_save", function ({ parent }) {
            expect.step("web_save");
            return parent();
        });
        await mountView({ type: "gantt", resModel: "hr.leave" });
        await openLeavePopover();

        // no action to carry the edit, so Save appears in their place
        await contains(NAME_INPUT).edit("Updated time off");
        await waitFor(SAVE_BTN);
        expect(queryAllTexts(`${FOOTER} button`)).toEqual(["Save", "Discard"]);

        await click(SAVE_BTN);
        await waitFor(DELETE_BTN);
        expect.verifySteps(["web_save"]);
        const [leave] = env["hr.leave"].read(leaveId, ["name"]);
        expect(leave.name).toBe("Updated time off");
    });
});

describe("leave split tool", () => {
    const SPLIT_TOOL = ".o_hr_holidays_gantt_pill_split_tool";

    function createLeave(env, values = {}) {
        const [employeeId] = env["hr.employee"].create([{ name: "Employee 1", active: true }]);
        const [typeId] = env["hr.work.entry.type"].create([{ name: "Paid Time Off" }]);
        env["hr.leave"].create([
            {
                name: "Time off",
                employee_id: employeeId,
                work_entry_type_id: typeId,
                date_from: "2025-01-06 08:00:00",
                date_to: "2025-01-09 17:00:00",
                state: "validate",
                ...values,
            },
        ]);
    }

    test("the scissors show when hovering an inner day boundary of a multi-day time off", async () => {
        const { env } = await makeMockServer();
        createLeave(env);
        // canSplitLeave is gated behind the officer group.
        onRpc("has_group", () => true);
        await mountView({ type: "gantt", resModel: "hr.leave" });

        // Nothing is shown until an inner day boundary of the pill is hovered.
        expect(SPLIT_TOOL).toHaveCount(0);

        // Hovering the left edge (a day boundary) of an inner day of the pill
        // snaps the scissors there.
        await hoverGridCell("07", "January 2025", "Employee 1");
        await waitFor(SPLIT_TOOL);
        expect(SPLIT_TOOL).toHaveCount(1);
        expect(`${SPLIT_TOOL} [data-icon='content_cut']`).toHaveCount(1);
    });

    test("the scissors do not show on the outer start of the time off", async () => {
        const { env } = await makeMockServer();
        createLeave(env);
        onRpc("has_group", () => true);
        await mountView({ type: "gantt", resModel: "hr.leave" });

        // The first day boundary is the pill's own start, not an inner cut.
        await hoverGridCell("06", "January 2025", "Employee 1");
        expect(SPLIT_TOOL).toHaveCount(0);
    });

    test("the scissors do not show for a single-day time off", async () => {
        const { env } = await makeMockServer();
        createLeave(env, {
            date_from: "2025-01-06 08:00:00",
            date_to: "2025-01-06 17:00:00",
        });
        onRpc("has_group", () => true);
        await mountView({ type: "gantt", resModel: "hr.leave" });

        // A single-day time off has no inner day boundary to cut on.
        await hoverGridCell("06", "January 2025", "Employee 1");
        expect(SPLIT_TOOL).toHaveCount(0);
    });
});
