import * as Order from "@point_of_sale/../tests/generic_helpers/order_widget_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as ProductScreenPos from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as NumberPopup from "@point_of_sale/../tests/generic_helpers/number_popup_util";
import * as ProductScreenResto from "@pos_restaurant/../tests/tours/utils/product_screen_util";
import * as ChromePos from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ChromeRestaurant from "@pos_restaurant/../tests/tours/utils/chrome";
import { inLeftSide } from "@point_of_sale/../tests/pos/tours/utils/common";
import { registry } from "@web/core/registry";
import { checkPreparationTicketData } from "@point_of_sale/../tests/pos/tours/utils/preparation_receipt_util";

const Chrome = { ...ChromePos, ...ChromeRestaurant };
const ProductScreen = { ...ProductScreenPos, ...ProductScreenResto };

function clickOrderButton() {
    return [
        ProductScreen.clickOrderButton(),
        Chrome.waitRequest(),
        ProductScreen.orderlinesHaveNoChange(),
    ].flat();
}

registry.category("web_tour.tours").add("PreparationDisplayTourResto", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Create first order
            FloorScreen.clickTable("5"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.clickDisplayedProduct("Water"),
            ProductScreen.orderlineIsToOrder("Water"),
            ProductScreen.orderlineIsToOrder("Coca-Cola"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            FeedbackScreen.clickNextOrder(),

            // Create second order
            FloorScreen.isShown(),
            FloorScreen.clickTable("4"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.orderlineIsToOrder("Coca-Cola"),
            clickOrderButton(),
            FloorScreen.clickTable("4"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            FeedbackScreen.clickNextOrder(),

            // Create third order
            FloorScreen.isShown(),
            FloorScreen.clickTable("4"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.clickDisplayedProduct("Water"),
            ProductScreen.clickDisplayedProduct("Minute Maid"),
            ProductScreen.orderlineIsToOrder("Coca-Cola"),
            ProductScreen.orderlineIsToOrder("Water"),
            ProductScreen.orderlineIsToOrder("Minute Maid"),
            clickOrderButton(),
            FloorScreen.clickTable("4"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickOrderline("Minute Maid"),
            ProductScreen.selectedOrderlineHas("Minute Maid", "1"),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.selectedOrderlineHas("Minute Maid", "0"),
            ProductScreen.orderlineIsToOrder("Minute Maid"),
            clickOrderButton(),
            FloorScreen.clickTable("4"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            FeedbackScreen.clickNextOrder(),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayTourResto2", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Create first order
            FloorScreen.clickTable("5"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.orderlineIsToOrder("Coca-Cola"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.orderlineIsToOrder("Coca-Cola"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.orderlinesHaveNoChange(),
            Chrome.clickPlanButton(),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayCancelOrderTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickDisplayedProduct("Test Food"),
            ProductScreen.orderlineIsToOrder("Test Food"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.orderlinesHaveNoChange(),
            ProductScreen.clickReview(),
            ProductScreen.clickControlButton("Cancel Order"),
            Dialog.confirm(),
            FloorScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayPaymentNotCancelDisplayTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Coca-Cola", "2"),
            ProductScreen.addInternalNote("To Serve"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Coca-Cola", "2"),
            ProductScreen.addInternalNote("To Serve"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.clickOrderline("Coca-Cola", "2"),
            ProductScreen.clickNumpad("1"),
            Order.hasLine({
                productName: "Coca-Cola",
                quantity: 1,
                withClass: ":eq(0)",
            }),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            Chrome.endTour(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_update_internal_note_of_order", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickSubcategory("Test-cat"),
            ProductScreen.clickDisplayedProduct("Demo Food"),
            ProductScreen.clickDisplayedProduct("Test Food"),
            ProductScreen.orderlineIsToOrder("Test Food"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.clickOrderline("Test Food"),
            ProductScreen.addInternalNote("Test Internal Notes"),
            ProductScreen.selectedOrderlineHas("Test Food", "1.0"),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.selectedOrderlineHas("Test Food", "0.0"),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.selectedOrderlineHas("Demo Food", "1.0"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.totalAmountIs("10"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_feedback_screen_after_unsent_order_dialog", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.clickPayButton(false),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            FeedbackScreen.clickNextOrder(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_order_preparation_preparation_printer", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Create new order, order it, and refund it
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Coca-Cola", "2"),
            ProductScreen.addOrderline("Water", "2"),
            checkPreparationTicketData([
                { name: "Coca-Cola", qty: 2 },
                { name: "Water", qty: 2 },
            ]),
            ProductScreen.clickOrderButton(),
            Chrome.closePrintingWarning(),
            FloorScreen.clickTable("5"),
            inLeftSide(ProductScreen.orderLineHas("Coca-Cola", "2")),
            inLeftSide(ProductScreen.orderLineHas("Water", "2")),
            checkPreparationTicketData(
                [
                    { name: "Coca-Cola", qty: 2 },
                    { name: "Water", qty: 2 },
                ],
                {
                    visibleInDom: ["CANCELLED"],
                    cancelled: true,
                }
            ),
            ProductScreen.clickControlButton("Cancel Order"),
            Dialog.confirm(),
            Order.doesNotHaveLine(),
            FloorScreen.isShown(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_order_preparation_preparation_display", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // Create new order, order 1 time and cancel it.
            FloorScreen.clickTable("2"),
            ProductScreen.addOrderline("Coca-Cola", "2"),
            ProductScreen.addOrderline("Water", "2"),
            ProductScreen.clickOrderButton(),
            Chrome.closePrintingWarning(),
            FloorScreen.clickTable("2"),
            ProductScreen.clickControlButton("Cancel Order"),
            Dialog.confirm(),
            Chrome.closePrintingWarning(),

            // Create new order, order 2 times and cancel it.
            FloorScreen.clickTable("2"),
            ProductScreen.addOrderline("Coca-Cola", "2"),
            ProductScreen.addOrderline("Water", "2"),
            clickOrderButton(),
            Chrome.closePrintingWarning(),
            FloorScreen.clickTable("2"),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.addOrderline("Minute Maid", "2"),
            clickOrderButton(),
            Chrome.closePrintingWarning(),
            FloorScreen.clickTable("2"),
            ProductScreen.clickControlButton("Cancel Order"),
            Dialog.confirm(),
            Chrome.closePrintingWarning(),
            Chrome.waitRequest(),
        ].flat(),
});

registry.category("web_tour.tours").add("test_table_merge_with_unsynced_order", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            // ----- Order 1 ----- //
            FloorScreen.clickTable("4"),
            ProductScreen.addOrderline("Coca-Cola", "3"),
            ProductScreen.addOrderline("Water", "3"),
            ProductScreen.clickOrderButton(),
            // ----- Order 2 (Empty Order) ----- //
            FloorScreen.clickTable("5"),
            ProductScreen.clickControlButton("Guests"),
            NumberPopup.enterValue("21"),
            NumberPopup.isShown("21"),
            Dialog.confirm(),
            Chrome.clickPlanButton(),
            // ----- Link Table 4 and Table 5 ----- //
            FloorScreen.linkTables("4", "5"),
            FloorScreen.isChildTable("4"),
            FloorScreen.clickTable("5"),
        ].flat(),
});

registry.category("web_tour.tours").add("PreparationDisplayCourseTour", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.clickCourseButton(),
            ProductScreen.clickDisplayedProduct("Coca-Cola"),
            ProductScreen.clickCourseButton(),
            ProductScreen.clickDisplayedProduct("Water"),
            ProductScreen.clickCourseButton(),
            ProductScreen.clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.fireCourseButtonHighlighted("Course 2"),
            ProductScreen.fireCourseButton(),
            Chrome.waitRequest(),
        ].flat(),
});

registry.category("web_tour.tours").add("applyBestComboMultiQty", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            FloorScreen.clickTable("5"),
            ProductScreen.addOrderline("Maki", "4"),
            ProductScreen.addOrderline("Coke", "1"),
            clickOrderButton(),
            FloorScreen.clickTable("5"),
            ProductScreen.clickApplyCombo(),
            Chrome.waitRequest(),
        ].flat(),
});
