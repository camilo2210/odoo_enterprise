import { Composer } from "@mail/core/common/composer";
import { contains, openDiscuss, start, startServer } from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";

import { beforeEach, describe, test } from "@odoo/hoot";
import { serializeDateTime } from "@web/core/l10n/dates";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { defineWhatsAppModels } from "@whatsapp/../tests/whatsapp_test_helpers";

const { DateTime } = luxon;

describe.current.tags("desktop");
defineWhatsAppModels();

beforeEach(() => {
    // Simulate real user interactions
    patchWithCleanup(Composer.prototype, {
        isEventTrusted() {
            return true;
        },
    });
});

test("'Contact Blocked' banner is visible only in blocked whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp",
        channel_type: "whatsapp",
        whatsapp_channel_blocked: true,
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-Thread-banner", {
        text: "This WhatsApp contact is blocked. Sending and receiving messages is disabled.",
    });

    // Non-blocked conversation should not have this banner
    const [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
    pyEnv["bus.bus"]._sendone(
        channel,
        "mail.record/insert",
        new Store()
            .add(pyEnv["discuss.channel"].browse(channelId), (res) =>
                res.attr("whatsapp_channel_blocked", false)
            )
            .as_dict()
    );
    await contains(".o-mail-Thread-banner", {
        count: 0,
        text: "This WhatsApp contact is blocked. Sending and receiving messages is disabled.",
    });
});

test("'Conversation Closed' banner must be visible only in deactivated whatsapp channels", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({
        name: "WhatsApp",
        channel_type: "whatsapp",
        whatsapp_channel_valid_until: serializeDateTime(DateTime.local().minus({ minutes: 1 })),
    });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-Thread-banner", {
        text: "This conversation has been closed as more than 24 hours have passed since the last message received.",
    });

    // Active conversation should not have this button
    const [channel] = pyEnv["discuss.channel"].search_read([["id", "=", channelId]]);
    pyEnv["bus.bus"]._sendone(
        channel,
        "mail.record/insert",
        new Store()
            .add(pyEnv["discuss.channel"].browse(channelId), (res) =>
                res.attr("whatsapp_channel_valid_until", DateTime.utc().plus({ days: 1 }).toSQL())
            )
            .as_dict()
    );
    await contains(".o-mail-Thread-banner", { count: 0 });
});
