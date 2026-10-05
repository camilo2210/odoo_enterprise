import { registry } from "@web/core/registry";
import * as PrepDisplay from "@pos_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";
import * as UrbanPiperPrepDisplay from "./utils/urbanpiper_preparation_display_util";

registry.category("web_tour.tours").add("test_preparation_display_future_delivery_order", {
    steps: () =>
        [
            PrepDisplay.hasOrderCard({
                productName: "Product 1",
                quantity: 1,
            }),
            PrepDisplay.checkOrderCardCount(1),
            UrbanPiperPrepDisplay.checkDeliveryState("Acknowledged"),
            UrbanPiperPrepDisplay.isFutureDeliveryOrder("#MNHLAW3L"),
            UrbanPiperPrepDisplay.clickDeliveryOrder("#MNHLAW3L"),
            PrepDisplay.setStage("Ready"),
            UrbanPiperPrepDisplay.clickDeliveryOrder("#MNHLAW3L"),
            PrepDisplay.setStage("Completed"),
            UrbanPiperPrepDisplay.clickDoneOnDeliveryOrder("#MNHLAW3L"),
        ].flat(),
});
