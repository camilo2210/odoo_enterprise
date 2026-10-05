import { expect, test } from "@odoo/hoot";
import { queryAllTexts } from "@odoo/hoot-dom";
import { mockTimeZone } from "@odoo/hoot-mock";

import { mountView } from "@web/../tests/web_test_helpers";
import { definePlanningModels, planningModels } from "./planning_mock_models";

class PlanningSlot extends planningModels.PlanningSlot {
    _records = [
        {
            id: 1,
            name: "Intervention 1",
            start_datetime: "2021-09-01 08:00:00",
            end_datetime: "2021-09-01 12:00:00",
            allocated_hours: 4,
            allocated_percentage: 100,
            role_id: 1,
            conflicting_slot_ids: [2, 3],
        },
        {
            id: 2,
            name: "Intervention 2",
            start_datetime: "2021-09-01 08:00:00",
            end_datetime: "2021-09-01 12:00:00",
            allocated_hours: 4,
            allocated_percentage: 100,
            role_id: 1,
            conflicting_slot_ids: [1, 3],
        },
        {
            id: 3,
            name: "Intervention 3",
            start_datetime: "2021-09-01 10:00:00",
            end_datetime: "2021-09-01 13:00:00",
            allocated_hours: 2,
            allocated_percentage: 66.67,
            role_id: false,
            conflicting_slot_ids: [1, 2, 4, 5, 6, 7],
        },
        {
            id: 4,
            name: "Intervention 4",
            start_datetime: "2021-09-01 12:30:00",
            end_datetime: "2021-09-01 17:30:00",
            allocated_hours: 5,
            allocated_percentage: 100,
            role_id: 1,
            conflicting_slot_ids: [3, 5, 6],
        },
        {
            id: 5,
            name: "Intervention 5",
            start_datetime: "2021-09-01 12:30:00",
            end_datetime: "2021-09-01 17:30:00",
            allocated_hours: 5,
            allocated_percentage: 100,
            role_id: false,
            conflicting_slot_ids: [3, 4, 6],
        },
        {
            id: 6,
            name: "Intervention 6",
            start_datetime: "2021-09-01 12:30:00",
            end_datetime: "2021-09-01 18:00:00",
            allocated_hours: 5.5,
            allocated_percentage: 100,
            role_id: false,
            conflicting_slot_ids: [3, 4, 5],
        },
        {
            id: 7,
            name: "Intervention 7",
            start_datetime: "2021-09-01 12:30:00",
            end_datetime: "2021-09-01 17:30:00",
            allocated_hours: 5,
            allocated_percentage: 100,
            role_id: false,
            conflicting_slot_ids: [3, 4, 5],
        },
    ];

    _views = {
        form: `<form><field name="conflicting_slot_ids" widget="conflicting_slot_ids"/></form>`,
    };
}

class PlanningRole extends planningModels.PlanningRole {
    _records = [{ id: 1, name: "Developer" }];
}

planningModels.PlanningSlot = PlanningSlot;
planningModels.PlanningRole = PlanningRole;

definePlanningModels();

test("display conflicting slot ids field in the form view", async () => {
    mockTimeZone(+1);
    await mountView({
        resId: 1,
        resModel: "planning.slot",
        type: "form",
    });

    expect(".o_field_conflicting_slot_ids[name=conflicting_slot_ids]").toHaveCount(1);
    expect(".o_field_conflicting_slot_ids > button").toHaveText(
        "2 conflicts"
    );
    expect(queryAllTexts(".o_field_conflicting_slot_ids")).toEqual([
        "2 conflicts\nIntervention 2 (9:00 AM - 1:00 PM) and other ones.",
    ]);
});

test("display 6 shifts in conflict", async () => {
    mockTimeZone(+1);
    await mountView({
        resId: 3,
        resModel: "planning.slot",
        type: "form",
    });

    expect(".o_field_conflicting_slot_ids[name=conflicting_slot_ids]").toHaveCount(1);
    expect(".o_field_conflicting_slot_ids > button").toHaveText(
        "6 conflicts"
    );
    expect(queryAllTexts(".o_field_conflicting_slot_ids")).toEqual([
        "6 conflicts\nIntervention 1 (9:00 AM - 1:00 PM) and other ones.",
    ]);
});
