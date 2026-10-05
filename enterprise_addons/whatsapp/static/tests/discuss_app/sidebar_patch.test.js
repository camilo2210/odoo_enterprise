import {
    click,
    contains,
    insertText,
    openDiscuss,
    start,
    startServer,
    triggerHotkey,
    MENU_ACTIVE_IDS,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { getOrigin } from "@web/core/utils/urls";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

describe.current.tags("desktop");
defineWhatsAppModels();

test("Can join whatsapp channels from the command palette", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create([
        {
            name: "WhatsApp 1",
            channel_type: "whatsapp",
        },
        {
            name: "WhatsApp 2",
            channel_type: "whatsapp",
            channel_member_ids: [
                Command.create({
                    unpin_dt: "2021-01-01 12:00:00",
                    last_interest_dt: "2021-01-01 10:00:00",
                    partner_id: serverState.partnerId,
                }),
            ],
        },
    ]);
    await start();
    await openDiscuss();
    await triggerHotkey("control+k");
    await contains(".o_command_name", { count: 4 });
    await contains(".o_command_name:eq(0):text('WhatsApp 2')");
    await contains(".o_command_name:eq(1):text('WhatsApp 1')");
    await contains(".o_command_name:eq(2):text('Mitchell Admin')");
    await contains(".o_command_name:eq(3):text('View hidden conversations')");
    await insertText(
        ".o_command_palette_search input[placeholder='Search conversations']",
        "WhatsApp 2"
    );
    await contains(".o_command_name", { count: 3 });
    await contains(".o_command_name:eq(0):text('WhatsApp 2')");
    await contains(".o_command_name:eq(1):text('Create Channel')");
    await contains(".o_command_name:eq(2):text('View hidden conversations')");
    await click(".o_command_name", { text: "WhatsApp 2" });
    await contains(".o-mail-MessagingMenuItem:has(:text('WhatsApp 2'))");
});

test("can unpin whatsapp channel", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    await start();
    await openDiscuss(MENU_ACTIVE_IDS.WHATSAPP);
    await click(
        ".o-mail-NotificationItem:has(:text('WhatsApp 1')):has(.o-mail-ThreadIcon[data-icon='oi_whatsapp']) [title='Chat Actions']"
    );
    await click(".o-dropdown-item:text('Hide Until New Message')");
    await contains(".o-mail-NotificationItem");
});

test("Message unread counter in whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    pyEnv["mail.message"].create({
        author_id: serverState.partnerId,
        body: "Hello!",
        model: "discuss.channel",
        res_id: channelId,
    });
    await start();
    await openDiscuss(MENU_ACTIVE_IDS.WHATSAPP);
    await contains(".o-mail-MessagingMenu-tab:has(:text(WhatsApp)) .badge:text(1)");
    await click("[title='Chat Actions']");
    await click("button:text('Mark Read')");
    await contains(".o-mail-MessagingMenu-tab:has(:text(WhatsApp)):not(:has(.badge:text(1)))");
});

test("Whatsapp - Sidebar channel icons should have the whatsapp partner's avatar", async () => {
    const pyEnv = await startServer();
    const [memberPartnerId, whatsappPartnerId] = pyEnv["res.partner"].create([
        { name: "Operator" },
        { name: "Demo" },
    ]);
    pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: memberPartnerId }),
            Command.create({ partner_id: whatsappPartnerId }),
        ],
        channel_type: "whatsapp",
        whatsapp_partner_id: whatsappPartnerId,
    });
    const [partner] = pyEnv["res.partner"].search_read([["id", "=", whatsappPartnerId]]);
    await start();
    await openDiscuss(MENU_ACTIVE_IDS.WHATSAPP);
    await contains(
        `.o-mail-MessagingMenuItem img[data-src='${getOrigin()}/web/image/res.partner/${whatsappPartnerId}/avatar_128?unique=${
            deserializeDateTime(partner.write_date).ts
        }']`
    );
});

test("cannot leave whatsapp channel if current user is last agent", async () => {
    const pyEnv = await startServer();
    const whatsappPartnerId = pyEnv["res.partner"].create({ name: "WhatsApp Customer" });
    const agentPartnerId = pyEnv["res.partner"].create({ name: "Batman" });
    pyEnv["discuss.channel"].create([
        {
            name: "WhatsApp 1",
            channel_type: "whatsapp",
            channel_member_ids: [
                Command.create({ partner_id: serverState.partnerId }),
                Command.create({ partner_id: whatsappPartnerId }),
            ],
            whatsapp_partner_id: whatsappPartnerId,
        },
        {
            name: "WhatsApp 2",
            channel_type: "whatsapp",
            channel_member_ids: [
                Command.create({ partner_id: serverState.partnerId }),
                Command.create({ partner_id: agentPartnerId }),
                Command.create({ partner_id: whatsappPartnerId }),
            ],
            whatsapp_partner_id: whatsappPartnerId,
        },
    ]);
    await start();
    await openDiscuss(MENU_ACTIVE_IDS.WHATSAPP);
    await click(".o-mail-NotificationItem:has(:text('WhatsApp 1')) [title='Chat Actions']");
    await contains(".dropdown-item:text(Invite People)");
    await contains(".dropdown-item:text('Leave Conversation')", { count: 0 });
    await click(".o-mail-NotificationItem:has(:text('WhatsApp 2')) [title='Chat Actions']");
    await click(".o-dropdown-item:contains('Leave Conversation')");
    await contains(
        ".modal-body:text('You are about to leave this whatsapp conversation and will no longer have access to it unless you are invited again. Are you sure you want to continue?')"
    );
    await click(".o_dialog button:text('Leave Conversation')");
    await contains(".o-mail-NotificationItem:has(:text('WhatsApp 2'))", { count: 0 });
});
