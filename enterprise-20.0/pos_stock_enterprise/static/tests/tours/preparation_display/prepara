import * as PrepDisplay from "@pos_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";
import * as StockPrepDisplay from "@pos_stock_enterprise/../tests/tours/preparation_display/utils/preparation_display_util";

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("PreparationDisplayFrontEndTour", {
    steps: () =>
        [
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: ["Combo Product 3", "Combo Product 5", "Combo Product 7"],
            }),
            PrepDisplay.clickOrderline("001", "Combo Product 3"),
            PrepDisplay.isStrickedOrderline("001", "Combo Product 3"),
            PrepDisplay.clickOrder("001"),
            PrepDisplay.setStage("Ready"),
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: "Combo Product 3",
            }),

            PrepDisplay.setStage("To prepare"),
            PrepDisplay.clickRecall(),
            PrepDisplay.hasOrderCard({
                orderNumber: "001",
                productName: "Office Combo",
                quantity: 1,
                comboLine: ["Combo Product 3", "Combo Product 5", "Combo Product 7"],
            }),
            StockPrepDisplay.hasStockOrderCard({
                productName: "Monitor Stand",
                lotSerialNumber: "SN: 147259",
            }),
        ].flat(),
});
