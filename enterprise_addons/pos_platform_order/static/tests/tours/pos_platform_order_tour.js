import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as PlatformOrder from "@pos_platform_order/../tests/tours/utils/pos_platform_order_utils";
import * as ChromePos from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ChromeRestaurant from "@pos_restaurant/../tests/tours/utils/chrome";
const Chrome = { ...ChromePos, ...ChromeRestaurant };
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_platform_order_flow", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            Chrome.clickOrders(),
            TicketScreen.nthRowContains(1, "Platform Order #001"),
            TicketScreen.nthRowContains(1, "New"),
            TicketScreen.doubleClickOrder("Platform Order #001"),
            TicketScreen.isShown(), // Should not redirect to FloorScreen
            TicketScreen.selectOrder("Platform Order #001"),
            PlatformOrder.orderButtonClick("Accept Order"),
            TicketScreen.nthRowContains(1, "Accepted"),
            PlatformOrder.orderButtonClick("Set Food Ready"),
            PlatformOrder.foodReadyButtonIsDisabled(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_platform_order_reject_flow", {
    steps: () =>
        [
            Chrome.startPoS(),
            Chrome.clickOrders(),
            TicketScreen.nbOrdersIs(2),
            TicketScreen.nthRowContains(2, "Platform Order #002"),
            TicketScreen.nthRowContains(2, "New"),
            TicketScreen.deleteOrder("Platform Order #002"),
            {
                content: "wait for 1000 ms",
                trigger: "body",
                run: async () => {
                    await new Promise((resolve) => setTimeout(resolve, 1000));
                },
            },
            Dialog.confirm(),
            Chrome.isSyncStatusConnected(),
            Chrome.waitRequest(),
            TicketScreen.nbOrdersIs(1),
            TicketScreen.nthRowContains(1, "Platform Order #001"),
            TicketScreen.selectFilter("Cancelled"),
            TicketScreen.nbOrdersIs(1),
            TicketScreen.nthRowContains(1, "Platform Order #002"),
            TicketScreen.nthRowContains(1, "Cancelled"),
        ].flat(),
});
