import * as PosHr from "@pos_hr/../tests/tours/utils/pos_hr_helpers";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as CashierSelectionPopup from "@pos_hr/../tests/tours/utils/cashier_selection_popup_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_pos_planning_tour_with_available_slots", {
    steps: () =>
        [
            Chrome.clickBtn("Open Register"),
            PosHr.loginScreenIsShown(),
            PosHr.clickLoginButton(),
            CashierSelectionPopup.has("More.."),
            CashierSelectionPopup.has("Pos Employee1", { subtitleContains: "Planning" }),
            CashierSelectionPopup.has("Pos Employee2", { subtitleContains: "Planning" }),
            CashierSelectionPopup.has("Mitchell Admin"),
            // Clicking on "More..." should reveal the full list of available employees.
            CashierSelectionPopup.has("More..", { run: "click" }),
            CashierSelectionPopup.hasNot("More.."),
            CashierSelectionPopup.has("Pos Employee1", { subtitleContains: "Planning" }),
            CashierSelectionPopup.has("Pos Employee2", { subtitleContains: "Planning" }),
            CashierSelectionPopup.has("Mitchell Admin"),
            // Ensure Pos Employee3 does not display "Planning" as subtitle, because no planning slot exists
            CashierSelectionPopup.hasNot("Pos Employee3", { subtitleContains: "Planning" }),
            Chrome.endTour(),
        ].flat(),
});
