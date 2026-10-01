import { expect, test } from "@odoo/hoot";
import { queryText } from "@odoo/hoot-dom";
import { mockTimeZone } from "@odoo/hoot-mock";

import { mountView } from "@web/../tests/web_test_helpers";
import { definePlanningModels, planningModels } from "@planning/../tests/planning_mock_models";

import {
    PlanningSlot as SalePlanningPlanningSlot,
    SaleOrderLine as SalePlanningSaleOrderLine,
} from "./sale_planning_mock_models";

class PlanningSlot extends SalePlanningPlanningSlot {
    _records = [
        {
            id: 1,
            conflicting_slot_ids: [2],
        },
        {
            id: 2,
            start_datetime: "2021-09-01 08:00:00",
            end_datetime: "2021-09-01 12:00:00",
            allocated_hours: 4,
            allocated_percentage: 100,
            sale_line_id: 1,
        },
    ];

    _views = {
        form: `<form><field name="conflicting_slot_ids" widget="conflicting_slot_ids"/></form>`,
    };
}

class SaleOrderLine extends SalePlanningSaleOrderLine {
    _records = [{ id: 1, name: "Sale Order Line 1" }];
}

planningModels.PlanningSlot = PlanningSlot;
planningModels.SaleOrderLine = SaleOrderLine;

definePlanningModels();

test("Test the conflict slot message content", async () => {
    mockTimeZone(+1);
    await mountView({
        resId: 1,
        resModel: "planning.slot",
        type: "form",
    });

    expect(".o_field_conflicting_slot_ids").toHaveCount(1);
    expect(".o_field_conflicting_slot_ids button").toHaveCount(1);
    expect(queryText(".o_field_conflicting_slot_ids button")).toBe(
        "1 conflicts"
    );
});
