import { mailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { contains, defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

class VoipDidNumberRequest extends models.Model {
    _name = "voip.did.number.request";

    new_comment = fields.Text();

    _records = [{ id: 1, new_comment: false }];
}

defineModels({ ...mailModels, VoipDidNumberRequest });

test.tags("desktop");

test("send button reacts before the comment field loses focus", async () => {
    await mountView({
        type: "form",
        resModel: "voip.did.number.request",
        resId: 1,
        arch: `
            <form>
                <field name="new_comment" widget="voip_number_request_comment"/>
                <button name="action_send_comment" type="object" string="Send Message"
                        invisible="not new_comment"/>
                <button name="action_send_comment" type="object" string="Send Message"
                        disabled="disabled" invisible="new_comment"/>
            </form>`,
    });

    expect("button[name='action_send_comment']").not.toBeEnabled();

    await contains("textarea").edit("A question", { confirm: false });
    expect("textarea").toBeFocused();
    expect("button[name='action_send_comment']").toBeEnabled();

    await contains("textarea").clear({ confirm: false });
    expect("textarea").toBeFocused();
    expect("button[name='action_send_comment']").not.toBeEnabled();
});
