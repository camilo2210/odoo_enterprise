import { test, expect } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { mockDate } from "@odoo/hoot-mock";

definePosModels();

test("preparePlanningList", async () => {
    const pos = await setupPosEnv();
    const employee = pos.models["hr.employee"].get(3);

    mockDate("2025-09-17 11:00:00");
    const planningList = pos.accessRight.preparePlanningList();

    expect(Object.keys(planningList)[0]).toBe(employee.resource_id.id.toString());
    expect(planningList[employee.resource_id.id]).toMatch(/Planning:/);
});

test("getCashierSelectionList", async () => {
    const pos = await setupPosEnv();
    const emp1 = pos.models["hr.employee"].get(2);
    const emp2 = pos.models["hr.employee"].get(3);

    mockDate("2025-09-17 11:00:00");
    const list = pos.accessRight.getCashierSelectionList([emp1, emp2]);

    expect(list[0].id).toBe(emp2.id);
    expect(list[0].subtitle).toMatch(/Planning:/);
});
