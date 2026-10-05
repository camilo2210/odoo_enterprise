import { test, expect } from "@odoo/hoot";
import { getUrbanPiperFilledOrder } from "@pos_urban_piper/../tests/unit/utils";
import { OrderInfoPopup } from "@pos_urban_piper/point_of_sale_override/components/popups/order_info_popup/order_info_popup";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { setupPosEnvForPrepDisplay } from "@pos_enterprise/../tests/unit/utils";

definePosModels();

test("getOrderDetails", async () => {
    const store = await setupPosEnvForPrepDisplay();
    const order = await getUrbanPiperFilledOrder(store);
    order.delivery_status = "dispatched";

    const comp = await mountWithCleanup(OrderInfoPopup, {
        props: { order, close: () => {}, previousOrderCount: 0 },
    });
    expect(await comp.getOrderDetails()).toEqual({
        channelOtp: "TST-1756819673",
        fulfilmentMode: "partner",
        paymentMode: "card",
        orderOtp: "123456",
    });
});
