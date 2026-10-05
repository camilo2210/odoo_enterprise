import {
    click,
    contains,
    defineMailModels,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { registry } from "@web/core/registry";

describe.current.tags("desktop");
defineMailModels();

const serviceRegistry = registry.category("services");
let lastLaunchArgs;
serviceRegistry.add("aiChatLauncher", {
    start() {
        return {
            launchAIChat(args) {
                lastLaunchArgs = args;
            },
        };
    },
}, { force: true });

test("File viewer AI button launches chat with attachment context", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    const attachmentId = pyEnv["ir.attachment"].create({
        name: "Doc.txt",
        mimetype: "text/plain",
        raw: "VGVzdA==",
        res_model: "res.partner",
        res_id: partnerId,
    });
    lastLaunchArgs = undefined;

    await start();
    await openFormView("res.partner", partnerId, {
        arch: `
            <form>
                <sheet></sheet>
                <chatter open_attachments="True"/>
            </form>`,
    });

    await click(`.o-mail-AttachmentContainer[aria-label="Doc.txt"] .o-mail-AttachmentCard-image`);
    await contains(".o-FileViewer");
    await contains(".o-FileViewer-headerButton [title='Ask AI']");
    await click(".o-FileViewer-headerButton [title='Ask AI']");

    expect(lastLaunchArgs).toEqual({
        interfaceKey: "file_viewer_ai_button",
        recordModel: "ir.attachment",
        recordId: attachmentId,
        channelTitle: "Doc.txt",
        aiChatSourceId: attachmentId,
    });
});
