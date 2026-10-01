import { livechatModels } from "@im_livechat/../tests/livechat_test_helpers";

import {
    click,
    contains,
    MENU_ACTIVE_IDS,
    openDiscuss,
    openMessagingMenu,
    setupChatHub,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test, expect } from "@odoo/hoot";
import { Command, defineModels, serverState } from "@web/../tests/web_test_helpers";
import { DiscussChannel } from "./mock_models/discuss_channel";
import { SocialAccount } from "./mock_models/social_account";
import { SocialMedia } from "./mock_models/social_media";

describe.current.tags("desktop");
defineModels({ ...livechatModels, DiscussChannel, SocialAccount, SocialMedia });

test("social live chat channel", async () => {
    const pyEnv = await startServer();
    const mediaId = pyEnv["social.media"].create({ name: "Facebook" });
    const accountId = pyEnv["social.account"].create({ name: "My Page", media_id: mediaId });
    const guestId = pyEnv["mail.guest"].create({ name: "Facebook User" });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId, livechat_member_type: "agent" }),
            Command.create({ guest_id: guestId, livechat_member_type: "visitor" }),
        ],
        channel_type: "livechat",
        livechat_social_account_id: accountId,
        name: "Facebook User (My Page)",
    });
    const standardGuestId = pyEnv["mail.guest"].create({ name: "Standard Guest" });
    const standardLivechatChannelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ partner_id: serverState.partnerId, livechat_member_type: "agent" }),
            Command.create({ guest_id: standardGuestId, livechat_member_type: "visitor" }),
        ],
        channel_type: "livechat",
        name: "No Social Account",
    });
    const messageValues = {
        message_type: "comment",
        model: "discuss.channel",
        res_id: channelId,
    };
    pyEnv["mail.message"].create([
        // history message (we don't have an author)
        { ...messageValues, author_id: false, body: "history message" },
        { ...messageValues, author_guest_id: guestId, body: "message of the visitor" },
        { ...messageValues, body: "message of the operator" },
    ]);
    setupChatHub({ folded: [channelId, standardLivechatChannelId] });
    await start();
    const mediaIcon = `img.o_social_livechat_media_thread_icon[data-src*='/web/image/social.media/${mediaId}/image']`;
    const pageImage = `[data-src*='/web/image/social.account/${accountId}/image']`;
    const guestAvatar = `img[alt='Thread Image'][data-src*='/web/image/mail.guest/${guestId}/avatar_128']`;
    const socialChatBubble = ".o-mail-ChatBubble:has(.o-mail-ChatBubble-counter)";

    // the avatar of the guest is used for the thread, as it identifies the person we talk to
    expect(`${socialChatBubble} ${guestAvatar}`).toHaveCount(1);
    await click(socialChatBubble);
    await contains(".o-mail-ChatWindow-header");
    expect(`.o-mail-ChatWindow-header ${guestAvatar}`).toHaveCount(1);

    await openDiscuss(channelId);

    await contains(".o-mail-Message", { count: 3 });

    expect(`.o-mail-DiscussContent-header ${guestAvatar}`).toHaveCount(1);
    // the logo of the social media replaces the im status of the visitor
    expect(`.o-mail-DiscussContent-header ${mediaIcon}`).toHaveCount(1);
    expect(".o-mail-DiscussContent-header .o-mail-ImStatus").toHaveCount(0);

    // show the page image in the composer
    expect(".o-mail-Composer-avatar").toHaveCount(1);
    expect(`.o-mail-Composer-avatar${pageImage}`).toHaveCount(1);

    // the messages we sent use the image and the name of the page
    const operator = ".o-mail-Message:contains('message of the operator')";
    expect(`${operator} .o-mail-Message-avatar${pageImage}`).toHaveCount(1);
    expect(`${operator} .o-mail-Message-author`).toHaveText(`My Page (${serverState.partnerName})`);

    // history messages have no author, only the name of the page is displayed
    const history = ".o-mail-Message:contains('history message')";
    expect(`${history} .o-mail-Message-avatar${pageImage}`).toHaveCount(1);
    expect(`${history} .o-mail-Message-author`).toHaveText("My Page");

    // the visitor keeps their own avatar and name
    const visitor = ".o-mail-Message:contains('message of the visitor')";
    expect(`${visitor} .o-mail-Message-avatar[data-src*='/web/image/mail.guest/']`).toHaveCount(1);
    expect(`${visitor} .o-mail-Message-author`).toHaveText("Facebook User");

    // the logo of the social media is also the icon in the messaging menu
    await openMessagingMenu(MENU_ACTIVE_IDS.LIVECHAT);
    const notificationItem =
        ".o-mail-MessagingMenuInDropdown .o-mail-NotificationItem:contains('Facebook User (My Page)')";
    const standardNotificationItem =
        ".o-mail-MessagingMenuInDropdown .o-mail-NotificationItem:contains('Standard Guest')";

    expect(notificationItem).toHaveCount(1);
    expect(standardNotificationItem).toHaveCount(1);

    expect(`${notificationItem} ${mediaIcon}`).toHaveCount(1);
    expect(`${standardNotificationItem} ${mediaIcon}`).toHaveCount(0);

    expect(`${notificationItem} .o-mail-ImStatus`).toHaveCount(0);
    expect(`${standardNotificationItem} .o-mail-ImStatus`).toHaveCount(1);
});

test("social live chat channel without operator is listed", async () => {
    const pyEnv = await startServer();
    pyEnv["res.users"].write([serverState.userId], {
        group_ids: pyEnv["res.groups"]
            .search_read([["id", "=", serverState.groupLivechatId]])
            .map(({ id }) => id),
    });
    const mediaId = pyEnv["social.media"].create({ name: "Facebook" });
    const accountId = pyEnv["social.account"].create({ name: "My Page", media_id: mediaId });
    const guestId = pyEnv["mail.guest"].create({ name: "Facebook User" });
    pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ guest_id: guestId, livechat_member_type: "visitor" }),
        ],
        channel_type: "livechat",
        livechat_failure: "no_agent",
        livechat_social_account_id: accountId,
        name: "Facebook User (My Page)",
    });
    await start();
    await openMessagingMenu(MENU_ACTIVE_IDS.LIVECHAT);
    await contains(".o-mail-NotificationItem:has(:text('Facebook User (My Page)'))");
});
