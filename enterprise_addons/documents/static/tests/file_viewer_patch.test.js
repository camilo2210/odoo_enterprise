import { DocumentsModels } from "@documents/../tests/helpers/data";
import {
    click,
    contains,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { test } from "@odoo/hoot";
import { defineModels } from "@web/../tests/web_test_helpers";

defineModels(DocumentsModels);

test("File viewer documents button: Add to Documents, Organize in Documents", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["ir.attachment"].create({
        mimetype: "text/plain",
        name: "Doc.txt",
        res_id: partnerId,
        res_model: "res.partner",
    });
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
    await click(".o-FileViewer-headerButton[title='Add to Documents']");
    await click(".o-FileViewer-headerButton[title='Organize in Documents']");
    await contains(".o_dialog .modal-header:text('Move: Doc.txt')");
});
