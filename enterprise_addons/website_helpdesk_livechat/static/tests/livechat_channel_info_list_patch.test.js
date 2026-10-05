import { contains, openDiscuss, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { Command, serverState } from "@web/../tests/web_test_helpers";
import { defineWebsiteHelpdeskLivechatModels } from "@website_helpdesk_livechat/../tests/website_helpdesk_livechat_test_helpers";

describe.current.tags("desktop");
defineWebsiteHelpdeskLivechatModels();

test("open tickets of the visitor are shown in the channel info list", async () => {
    const pyEnv = await startServer();
    const customerPartnerId = pyEnv["res.partner"].create({ name: "Bob" });
    pyEnv["helpdesk.ticket"].create({ name: "Bob cannot log in", partner_id: customerPartnerId });
    const channelId = pyEnv["discuss.channel"].create({
        channel_member_ids: [
            Command.create({ livechat_member_type: "agent", partner_id: serverState.partnerId }),
            Command.create({ livechat_member_type: "visitor", partner_id: customerPartnerId }),
        ],
        channel_type: "livechat",
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-livechat-ChannelInfoList h6:text('Open tickets')");
    await contains(
        ".o-livechat-ChannelInfoList a[data-oe-model='helpdesk.ticket']:text('Bob cannot log in')"
    );
});
