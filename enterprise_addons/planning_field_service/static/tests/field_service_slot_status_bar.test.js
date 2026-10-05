import { describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";

import { mountView, onRpc, fields } from "@web/../tests/web_test_helpers";

import { definePlanningModels, planningModels } from "@planning/../tests/planning_mock_models";

describe.current.tags("desktop");

class PlanningSlot extends planningModels.PlanningSlot {
    partner_id = fields.Many2one({ relation: "res.partner" });
    state = fields.Selection({
        selection: [
            ["1_draft", "Draft"],
            ["2_published", "Scheduled"],
            ["3_in_progress", "In Progress"],
            ["4_completed", "Completed"],
        ],
    });
}
planningModels.PlanningSlot = PlanningSlot;
PlanningSlot._records = [
    {
        id: 1,
        name: "shift",
        state: "1_draft",
        start_datetime: "2023-10-10 09:00:00",
        end_datetime: "2023-10-10 17:00:00",
    },
];
PlanningSlot._views = {
    form: `
        <form js_class="planning_form">
            <field name="start_datetime"/>
            <field name="end_datetime"/>
            <field name="partner_id"/>
            <field name="state" widget="field_service_slot_status_bar" options="{'clickable': true}"/>
        </form>
    `,
};
definePlanningModels();

test("test service_slot_status_bar widget", async () => {
    onRpc("action_complete", function ({ args, kwargs, model }) {
        expect(args[0]).toBe(1);
        expect(kwargs.from_status_bar).toBe(true);
        expect.step("shift_action_complete");
        return this.env[model].write(args[0], { state: "4_completed" });
    });

    await mountView({
        type: "form",
        resModel: "planning.slot",
        resId: 1,
    });

    // Change state to 'in_progress'
    await click("button[data-value='3_in_progress']");
    expect(".modal-content").toHaveCount(0, {
        message: "The state must be set to 'Completed' to open the confirmation dialog",
    });

    // Change state to 'completed' but without partner
    await click("button[data-value='4_completed']");
    expect(".modal-content").toHaveCount(0, {
        message: "The shift must contain a partner to open the confirmation dialog ",
    });

    // Change state to 'completed' with partner
    await click("button[data-value='3_in_progress']");
    await click(".o_field_widget[name='partner_id'] input");
    await animationFrame();
    await click(".ui-autocomplete .ui-menu-item:first-child");
    await animationFrame();
    await click("button[data-value='4_completed']");
    await animationFrame();
    expect(".modal-content").toHaveCount(1, {
        message:
            "The confirmation dialog must appear as the shift is marked as completed and has a partner set",
    });

    // Test 'Discard' button
    await click(".modal-footer button:contains('Discard')");
    await animationFrame();
    expect("button[data-value='4_completed']").not.toBeFocused();
    expect(".modal-content").toHaveCount(0);
    await click("button[data-value='3_in_progress']");
    await animationFrame();

    // Test 'Complete' button
    await click("button[data-value='4_completed']");
    await animationFrame();
    await click(".modal-footer button:contains('Complete')");
    await animationFrame();
    expect("button[data-value='4_completed']").toHaveClass("o_arrow_button_current");
    expect.verifySteps(["shift_action_complete"]);
});
