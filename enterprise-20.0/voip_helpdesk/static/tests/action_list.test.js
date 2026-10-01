import { describe, test } from "@odoo/hoot";

import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { openRecentContactSearch, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { onRpc } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("TicketButton is hidden when user doesn't have helpdesk user group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", () => false);
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:text('Test Partner')");
    await contains("button.o-voip-ActionButton[title='Go to']");
    await contains("button.o-voip-ActionButton[title='Create']", { count: 0 });
});

test("TicketButton is shown when user has helpdesk user group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "helpdesk.group_helpdesk_user";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:text('Test Partner')");
    await click("button.o-voip-ActionButton[title='Create']");
    await contains("span.o-dropdown-item i[data-icon='support']");
    await contains("span.o-dropdown-item span:text('Ticket')");
});

test("TicketButton is shown with title 'View ticket' and icon 'support' when user has helpdesk user group", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "Test Partner",
        phone: "+1-555-123-4567",
        commercial_partner_ticket_count: 1,
    });
    onRpc("has_group", (args) => {
        const group = args.args[1];
        return group === "helpdesk.group_helpdesk_user";
    });
    await start();
    await openRecentContactSearch("Test Partner");
    await click(".o-voip-TabEntry:text('Test Partner')");
    await click("button.o-voip-ActionButton[title='Go to']");
    await contains("span.o-dropdown-item i[data-icon='support']");
    await contains("span.o-dropdown-item span:text('Ticket')");
});
