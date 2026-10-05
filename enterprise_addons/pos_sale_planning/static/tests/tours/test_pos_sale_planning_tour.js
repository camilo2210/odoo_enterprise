import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PlanningSlotPopup from "@pos_sale_planning/../tests/tours/utils/planning_slot_selection_popup_util";
import { negateStep } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

/**
 * Tour 1: resource payment method WITH explicitly linked resources.
 *
 * - Only the two linked resources (Meeting Room A, Conference Room B) appear
 *   in the popup, not Training Room C.
 * - Search filters resources by name.
 * - Selecting a resource creates a payment line named "<method> (<slot>)".
 */
registry.category("web_tour.tours").add("test_pos_sale_planning_with_linked_resources", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Test Product"),
            ProductScreen.clickPayButton(),
            PaymentScreen.isShown(),
            PaymentScreen.clickPaymentMethod("Resource (Linked)"),
            Dialog.is({ title: "Choose a slot" }),
            // Only linked resources should appear
            Dialog.bodyIs("Meeting Room A"),
            Dialog.bodyIs("Conference Room B"),
            negateStep(Dialog.bodyIs("Training Room C")),
            // Search filters by resource name
            PlanningSlotPopup.searchInPopup("Conference"),
            negateStep(Dialog.bodyIs("Meeting Room A")),
            Dialog.bodyIs("Conference Room B"),
            // Clear search, then select a resource
            PlanningSlotPopup.searchInPopup(""),
            PlanningSlotPopup.clickResourceInPopup("Meeting Room A"),
            // Payment line name includes the slot display name in parentheses
            PaymentScreen.selectedPaymentlineHas("Resource (Linked) (Slot Partner)", "11.5"),
            Chrome.endTour(),
        ].flat(),
});

/**
 * Tour 2: resource payment method WITHOUT linked resources (all resources).
 *
 * - All resources with active slots appear in the popup.
 * - Selecting one creates a correctly formatted payment line.
 */
registry.category("web_tour.tours").add("test_pos_sale_planning_without_linked_resources", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            ProductScreen.clickDisplayedProduct("Test Product"),
            ProductScreen.clickPayButton(),
            PaymentScreen.isShown(),
            PaymentScreen.clickPaymentMethod("Resource (All)"),
            Dialog.is({ title: "Choose a slot" }),
            // All three resources with active slots should appear
            Dialog.bodyIs("Meeting Room A"),
            Dialog.bodyIs("Conference Room B"),
            Dialog.bodyIs("Training Room C"),
            // Select a resource and verify the payment line format
            PlanningSlotPopup.clickResourceInPopup("Training Room C"),
            PaymentScreen.selectedPaymentlineHas("Resource (All) (Slot Partner)", "11.5"),
            Chrome.endTour(),
        ].flat(),
});
