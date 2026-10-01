import { describe, test } from "@odoo/hoot";
import {
    click,
    contains,
    openMessagingMenu,
    start,
    startServer,
    MENU_ACTIVE_IDS,
} from "@mail/../tests/mail_test_helpers";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

describe.current.tags("desktop");
defineWhatsAppModels();

test("WhatsApp channel chat windows should have whatsapp icon", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "WhatsApp User" });
    pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        whatsapp_partner_id: partnerId,
    });
    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.WHATSAPP);
    await click(".o-mail-NotificationItem");
    await contains(".o-mail-ChatWindow-header [data-icon='oi_whatsapp']");
});
