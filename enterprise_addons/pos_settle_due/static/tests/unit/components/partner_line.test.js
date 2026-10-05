import { animationFrame, expect, queryOne, test } from "@odoo/hoot";
import { click, queryAllTexts, waitFor } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupAndMountPosApp, setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import * as utils from "@point_of_sale/../tests/unit/ui_utils";

definePosModels();

test.tags("mobile");
test("partner balance status", async () => {
    const store = await setupAndMountPosApp();
    const partner = store.models["res.partner"].get(5);
    partner.total_due = 150;
    await utils.clickPartnerButton();
    // with outstanding balance.
    const partnerDue = queryOne(".partner-info:contains(User on budget) .partner-due");
    expect(partnerDue).toHaveText("Due: $ 150.00");
    expect(partnerDue).toHaveClass("border-danger");
    // credit balance (deposit).
    partner.total_due = -21;
    await animationFrame();
    expect(partnerDue).toHaveText("Deposit: $ 21.00");
    expect(partnerDue).toHaveClass("border-success");
});

test("deposit money is available when the customer has a due", async () => {
    const store = await setupPosEnv();
    const partner = store.models["res.partner"].get(5);
    partner.total_due = 7043;
    partner.invoices_amount_due = 7043;
    partner.pos_orders_amount_due = 0;

    await mountWithCleanup(PartnerLine, {
        props: {
            close: () => {},
            partner,
            isSelected: false,
            isBalanceDisplayed: true,
            onClickEdit: () => {},
            onClickUnselect: () => {},
            onClickPartner: () => {},
            onClickOrders: () => {},
        },
    });
    await click(".dropdown-toggle");
    await waitFor(".o-dropdown-item");

    const items = queryAllTexts(".o-dropdown-item");
    expect(items).toInclude("Settle invoices");
    expect(items).toInclude("Deposit money");
});
