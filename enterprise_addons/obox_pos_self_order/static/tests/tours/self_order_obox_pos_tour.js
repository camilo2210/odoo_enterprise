import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as ProductScreenPos from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ProductScreenResto from "@pos_restaurant/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import { checkPreparationTicketData } from "@point_of_sale/../tests/pos/tours/utils/preparation_receipt_util";

const ProductScreen = { ...ProductScreenPos, ...ProductScreenResto };

registry.category("web_tour.tours").add("test_pos_self_order_preparation_pos", {
    steps: () =>
        [
            ...Chrome.startPoS(),
            Chrome.clickOrders(),
            ...TicketScreen.selectOrder(115.0),
            ...TicketScreen.loadSelectedOrder(),
            checkPreparationTicketData([{ name: "Coca-Cola", qty: 1 }]),
            ProductScreen.clickOrderButton(),
            Chrome.clickOrders(),
            ...TicketScreen.selectOrder(115.0),
            ...TicketScreen.loadSelectedOrder(),
            ...ProductScreen.clickPayButton(),
            ...PaymentScreen.clickPaymentMethod("Bank"),
            ...PaymentScreen.clickValidate(),
            ...FeedbackScreen.isShown(),
            FeedbackScreen.clickNextOrder(),
        ].flat(),
});
