import { animationFrame, test, waitFor, waitUntil } from "@odoo/hoot";
import { click, setInputFiles, press } from "@odoo/hoot-dom";
import {
    defineModels,
    mountView,
    contains,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { DocumentsMixinTestModel } from "./helpers/data";
import { Thread } from "@mail/core/common/thread_model";

const testModelFormview = `
<form>
    <sheet>
        <div class="oe_button_box" name="button_box">
            <button type="object" class="oe_stat_button" icon="star" icon_class="oi-filled">
                <field name="document_count" widget="statinfo" string="Documents"/>
            </button>
        </div>
        <group>
            <field name="name"/>
        </group>
    </sheet>
    <chatter/>
</form>`;

defineModels([DocumentsMixinTestModel]);
defineMailModels();

test.tags("desktop");
test("documents count change with adding/deleting attachments to chatter", async function () {
    patchWithCleanup(Thread.prototype, {
        setup() {
            super.setup(...arguments);
            this.is_documents_mixin = true;
        },
    });
    const demo = {
        id: 1,
        name: "My Specific Test Record",
        document_count: 0,
    };
    onRpc("/mail/attachment/upload", async (request) => {
        demo.document_count += 1;
    });
    onRpc("/mail/attachment/delete", async (request) => {
        demo.document_count -= 1;
    });
    DocumentsMixinTestModel._records = [demo];

    await mountView({
        actionMenus: {},
        type: "form",
        resModel: "documents.mixin.test.model",
        arch: testModelFormview,
        resId: 1,
    });

    await contains("button.o-mail-Chatter-attachFiles").click();
    await setInputFiles([new File(["fake_file"], "fake_file.tiff", { type: "text/plain" })]);

    const statinfo_val = await waitFor("span.o_stat_info.o_stat_value");
    await waitUntil(() => statinfo_val.textContent == "1");
    await click(".o-mail-Attachment-unlink");
    await contains("button:text('Delete Attachment')").click();

    await waitUntil(() => statinfo_val.textContent == "0");

    await contains(".o-mail-Chatter-sendMessage").click();
    await click('button[name="upload-files"]');
    await setInputFiles([new File(["fake_file_2"], "fake_file_2.tiff", { type: "text/plain" })]);
    await contains("textarea.o-mail-Composer-input").click();
    await animationFrame();
    await press(["ctrl", "Enter"]);
    await waitUntil(() => statinfo_val.textContent == "1");
});
