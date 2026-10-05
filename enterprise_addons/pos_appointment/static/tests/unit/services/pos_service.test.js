import { test, expect, describe } from "@odoo/hoot";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";

definePosModels();

describe("pos_store", () => {
    test("manageBookings", async () => {
        const store = await setupPosEnv();
        let screenName = null;
        let params = null;
        patchWithCleanup(store.router, {
            navigate(routeName, routeParams) {
                if (routeName === "ActionScreen") {
                    screenName = routeName;
                    params = routeParams;
                }
                return super.navigate(...arguments);
            },
        });
        await store.manageBookings();
        expect(screenName).toEqual("ActionScreen");
        expect(params).toEqual({ actionName: "manage-booking", viewMode: "" });
    });
});
