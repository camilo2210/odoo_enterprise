import { expect, test } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { mountWithCleanup, patchWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { ActionScreen } from "@point_of_sale/app/screens/action_screen";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

definePosModels();

test("ActionScreen => useEffect", async () => {
    const store = await setupPosEnv();
    onRpc("calendar.event", "action_open_booking_gantt_view", () => ({
        type: "ir.actions.act_window",
        name: "Gantt View",
    }));
    let actionCalled = null;
    patchWithCleanup(store.action, {
        async doAction(action) {
            actionCalled = action;
        },
    });
    await mountWithCleanup(ActionScreen, { props: { actionName: "manage-booking" } });
    expect(actionCalled).toEqual({
        type: "ir.actions.act_window",
        name: "Gantt View",
    });
});
