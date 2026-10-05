import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";
import { describe, test } from "@odoo/hoot";
import { openRecentContactSearch } from "@voip/../tests/voip_test_helpers";
import { setupVoipCRMTests } from "@voip_crm/../tests/voip_crm_test_helpers";

describe.current.tags("desktop");
setupVoipCRMTests();

test("LeadButton is hidden when user doesn't have sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", () => false);
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await contains("button[title='Create a lead']", { count: 0 });
});

test("LeadButton is shown when user has sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_salesman";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await click("button[title='Create']");
    await contains("span.o-dropdown-item i[data-icon='star'].oi-filled");
    await contains("span.o-dropdown-item span:contains('Lead')");
});

test("LeadButton is shown with title 'View lead' and icon 'star' when user has sales team groups", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
        commercial_partner_opportunity_count: 1,
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "sales_team.group_sale_salesman";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:contains('Test Partner')");
    await click("button[title='Go to']");
    await contains("span.o-dropdown-item i[data-icon='star'].oi-filled");
    await contains("span.o-dropdown-item span:contains('Lead')");
});
