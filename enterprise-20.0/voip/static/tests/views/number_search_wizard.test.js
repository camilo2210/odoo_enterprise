import { mailModels } from "@mail/../tests/mail_test_helpers";
import { animationFrame, expect, test } from "@odoo/hoot";
import { pointerDown, pointerUp, queryOne } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    mockService,
    models,
    mountViewInDialog,
} from "@web/../tests/web_test_helpers";

class NumberSearchWizard extends models.Model {
    _name = "voip.did.number.search.wizard";

    starts_with = fields.Char();

    _records = [{ id: 1, starts_with: "123" }];
}

defineModels({ ...mailModels, NumberSearchWizard });

test("number search action is captured before the focused criterion is committed", async () => {
    mockService("action", {
        doActionButton(params) {
            expect.step(params.name);
        },
    });
    await mountViewInDialog({
        type: "form",
        resModel: "voip.did.number.search.wizard",
        resId: 1,
        arch: `
            <form>
                <field name="starts_with"/>
                <footer>
                    <button name="action_search" type="object" string="Search"/>
                </footer>
            </form>`,
    });

    await contains("input").click();
    const searchButton = queryOne("button[name='action_search']");
    await pointerDown(searchButton);
    expect("input").toBeFocused();
    await pointerUp(searchButton);
    await animationFrame();

    expect.verifySteps(["action_search"]);
});
