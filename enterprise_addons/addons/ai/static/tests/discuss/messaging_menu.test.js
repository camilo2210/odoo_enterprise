import {
    click,
    contains,
    MENU_ACTIVE_IDS,
    openDiscuss,
    openMessagingMenu,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { test } from "@odoo/hoot";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineAIModels } from "../ai_test_helpers";

defineAIModels();

test("Can open a new AI chat from the messaging menu AI tab", async () => {
    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.AI_CHAT);
    await click("button:has([data-icon='add']):text('Chat')");
    await contains(".o-mail-ChatWindow-displayName:text('Test AI Agent')");
});

test("AI tab has an unread filter", async () => {
    const pyEnv = await startServer();
    const [alphaPartnerId, betaPartnerId] = pyEnv["res.partner"].create([
        { name: "Alpha AI" },
        { name: "Beta AI" },
    ]);
    const [alphaAgentId, betaAgentId] = pyEnv["ai.agent"].create([
        { name: "Alpha AI", partner_id: alphaPartnerId },
        { name: "Beta AI", partner_id: betaPartnerId },
    ]);
    const [alphaChannelId, betaChannelId] = pyEnv["discuss.channel"].create([
        {
            ai_agent_id: alphaAgentId,
            channel_member_ids: [
                Command.create({ partner_id: serverState.partnerId }),
                Command.create({ partner_id: alphaPartnerId }),
            ],
            channel_type: "ai_chat",
            name: "Alpha AI",
        },
        {
            ai_agent_id: betaAgentId,
            channel_member_ids: [
                Command.create({ partner_id: serverState.partnerId }),
                Command.create({ partner_id: betaPartnerId }),
            ],
            channel_type: "ai_chat",
            name: "Beta AI",
        },
    ]);
    const [, betaMessageId] = pyEnv["mail.message"].create([
        {
            author_id: alphaPartnerId,
            body: "hello",
            model: "discuss.channel",
            res_id: alphaChannelId,
        },
        { author_id: betaPartnerId, body: "hi", model: "discuss.channel", res_id: betaChannelId },
    ]);
    const [betaMemberId] = pyEnv["discuss.channel.member"].search([
        ["channel_id", "=", betaChannelId],
        ["partner_id", "=", serverState.partnerId],
    ]);
    // Beta AI is marked read: its separator is past its last message.
    pyEnv["discuss.channel.member"].write([betaMemberId], {
        new_message_separator: betaMessageId + 1,
    });
    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.AI_CHAT);
    await contains(".o-mail-NotificationItem", { count: 2 });
    await contains(".o-mail-NotificationItem:has(:text('Alpha AI'))");
    await contains(".o-mail-NotificationItem:has(:text('Beta AI'))");
    await click("button:text('Unread')");
    await contains("button.o-active:text('Unread')");
    await contains(".o-mail-NotificationItem", { count: 1 });
    await contains(".o-mail-NotificationItem:has(:text('Alpha AI'))");
});

test("AI tab agent plugin filter works alongside chip filters", async () => {
    const pyEnv = await startServer();
    const [alphaPartnerId, betaPartnerId] = pyEnv["res.partner"].create([
        { name: "Alpha AI" },
        { name: "Beta AI" },
    ]);
    const [alphaAgentId, betaAgentId] = pyEnv["ai.agent"].create([
        { name: "Alpha AI", partner_id: alphaPartnerId },
        { name: "Beta AI", partner_id: betaPartnerId },
    ]);
    const alphaChannelIds = pyEnv["discuss.channel"].create(
        Array.from({ length: 22 }, (_, i) => ({
            ai_agent_id: alphaAgentId,
            channel_member_ids: [
                Command.create({ partner_id: serverState.partnerId }),
                Command.create({ partner_id: alphaPartnerId }),
            ],
            channel_type: "ai_chat",
            name: `Alpha chat ${i}`,
        }))
    );
    pyEnv["discuss.channel"].create({
        ai_agent_id: betaAgentId,
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId }),
            Command.create({ partner_id: betaPartnerId }),
        ],
        channel_type: "ai_chat",
        name: "Beta chat",
    });
    pyEnv["mail.message"].create({
        author_id: alphaPartnerId,
        body: "hello",
        model: "discuss.channel",
        res_id: alphaChannelIds[0],
    });
    await start();
    await openDiscuss(MENU_ACTIVE_IDS.AI_CHAT);
    await contains(".o-mail-NotificationItem", { count: 20 });
    await click("button[aria-label='Filters']");
    await click(".dropdown-item:text('Beta AI')");
    await contains(".o-mail-NotificationItem");
    await contains(".o-mail-NotificationItem:has(:text('Beta chat'))");
    await click("button[aria-label='Filters']");
    await click(".dropdown-item:text('Alpha AI')");
    await contains(".o-mail-NotificationItem:contains('Alpha chat')", { count: 22 });
    await click("button:text('Unread')");
    await contains("button.o-active:text('Unread')");
    await contains(".o-mail-NotificationItem", { count: 1 });
    await contains(".o-mail-NotificationItem:has(:text('Alpha chat 0'))");
});
