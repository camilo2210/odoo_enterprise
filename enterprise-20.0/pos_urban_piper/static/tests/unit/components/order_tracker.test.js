import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OrderTrackerDropdown } from "@point_of_sale/app/components/order_tracker_dropdown/order_tracker_dropdown";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("handleToggle", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const comp = await mountWithCleanup(OrderTrackerDropdown, {});
    const aggregator = store.models["urbanpiper.store.aggregator"].get(1);
    expect(aggregator.is_online).toBe(true);
    await comp.handleToggle(aggregator);
    expect(aggregator.is_online).toBe(false);
});
