import {
    SIZES,
    click,
    contains,
    openDiscuss,
    patchUiSize,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

describe.current.tags("desktop");
defineWhatsAppModels();

test("Basic topbar rendering for whatsapp channels", async () => {
    const pyEnv = await startServer();
    const whatasspUser = pyEnv["res.partner"].create({ name: "Branden Freeman" });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: whatasspUser }),
        ],
        channel_type: "whatsapp",
        name: "WhatsApp 1",
        whatsapp_partner_id: whatasspUser,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-DiscussContent-header .o-mail-ThreadIcon[data-icon='oi_whatsapp']");
    await contains(".o-mail-DiscussContent-threadName", { value: "WhatsApp 1" });
    await waitFor(".o-mail-DiscussContent-header button:count(5)");
    await contains(".o-mail-DiscussContent-header button:eq(0)[title='Mute Conversation']");
    await contains(".o-mail-DiscussContent-header button:eq(1)[title='Search Messages']");
    await contains(".o-mail-DiscussContent-header button:eq(2)[title='Attachments']");
    await contains(".o-mail-DiscussContent-header button:eq(3)[title='Pinned Messages']");
    await contains(".o-mail-DiscussContent-header button:eq(4)[title='Members']");
});

test("whatsapp conversations: basic actions rendering", async () => {
    const pyEnv = await startServer();
    const whatsappUser = pyEnv["res.partner"].create({ name: "Branden Freeman" });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: whatsappUser }),
        ],
        channel_type: "whatsapp",
        name: "WhatsApp 1",
        whatsapp_partner_id: whatsappUser,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-DiscussContent-threadName", { value: "WhatsApp 1" });
    await click("[title='Chat Actions']");
    await contains(".o-dropdown-item", { count: 6 });
    await contains(".o-dropdown-item:text('Invite People')");
    await contains(".o-dropdown-item:text('Add to Favorites')");
    await contains(".o-dropdown-item:text('Mute Conversation')");
    await contains(".o-dropdown-item:text('View Recordings')");
    await contains(".o-dropdown-item:text('Advanced Settings')");
    await contains(".o-dropdown-item:text('Hide Until New Message')");
});

test("Invite users into whatsapp channel", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
    });
    const partnerId = pyEnv["res.partner"].create({ name: "WhatsApp User" });
    pyEnv["res.users"].create({ partner_id: partnerId });
    await start();
    await openDiscuss(channelId);
    await contains(".o-discuss-ChannelMemberList"); // wait for auto-open of this panel
    await click("button[title='Add People']");
    await click(".o-discuss-ChannelInvitation-selectable");
    await click(".o-discuss-ChannelInvitation button:text('Invite'):enabled");
    await contains(".o_mail_notification", { text: "invited WhatsApp User to the channel" });
});

test("Shows whatsapp user in member list", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "WhatsApp Partner" });
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp 1",
        channel_type: "whatsapp",
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partnerId }),
        ],
        whatsapp_partner_id: partnerId,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-discuss-ChannelMember.cursor-pointer", { text: "Mitchell Admin" });
    await contains(".o-discuss-ChannelMemberList h6", { text: "WhatsApp User" });
    await contains(".o-discuss-ChannelMember.cursor-pointer", {
        text: "WhatsApp Partner",
        contains: [".o-mail-ImStatus[title='WhatsApp User']"],
    });
});

test("Mobile has WhatsApp category", async () => {
    const pyEnv = await startServer();
    patchUiSize({ size: SIZES.SM });
    pyEnv["discuss.channel"].create({ name: "WhatsApp 1", channel_type: "whatsapp" });
    await start();
    await openDiscuss();
    await click(".o-mail-MessagingMenu-navbar button", { text: "WhatsApp" });
    await contains(".o-mail-NotificationItem", { text: "WhatsApp 1" });
});

test("Can search whatsapp conversations on mobile", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create({
        name: "slytherins",
        channel_type: "whatsapp",
    });
    patchUiSize({ size: SIZES.SM });
    await start();
    await openDiscuss();
    await click("button", { text: "WhatsApp" });
    await click(".o-mail-DiscussSearch-inputContainer");
    await click(".o-mail-NotificationItem-name:text(slytherins)");
    await contains(".o-mail-ChatWindow-header div[title='slytherins']");
});

test("open whatsapp user's partner profile", async () => {
    const pyEnv = await startServer();
    const partner = pyEnv["res.partner"].create({ name: "Branden Freeman" });
    const channel = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: partner }),
        ],
        channel_type: "whatsapp",
        whatsapp_partner_id: partner,
    });
    pyEnv["mail.message"].create({
        author_id: partner,
        model: "discuss.channel",
        message_type: "whatsapp_message",
        body: "<p>HELLO</p>",
        res_id: channel,
    });

    await start();
    await openDiscuss(channel);
    await click(".o-mail-Message-author");
    await click("button:text('View Profile')");
    await contains("div.o_field_widget input:value(Branden Freeman)");
});
