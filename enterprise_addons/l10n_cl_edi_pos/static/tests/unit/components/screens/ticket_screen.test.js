import { test, expect } from "@odoo/hoot";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { defineL10nCLPosEdiModels } from "../../data/generate_model_definitions";

defineL10nCLPosEdiModels();

test("showInvoiceButton", async () => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const ticketScreen = await mountWithCleanup(TicketScreen);
    ticketScreen.onClickOrder(order);
    order.state = "paid";
    // In CL localisation, invoice button should not be visble even when order.state = "paid";
    expect(ticketScreen.showInvoiceButton).toBe(false);
});
