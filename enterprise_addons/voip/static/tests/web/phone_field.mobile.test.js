import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockUserAgent } from "@odoo/hoot-mock";
import {
    click,
    contains,
    openFormView,
    registerArchs,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Voip } from "@voip/core/web/voip_service";
import { Fake } from "@voip/../tests/mock_server/mock_models/fake";
import { defineModels, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";

describe.current.tags("mobile");
setupVoipTests();
defineModels({ Fake });

beforeEach(() => {
    mockUserAgent("android");
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
    registerArchs({
        "fake,false,form": `
            <form string="Fake" edit="0">
                <sheet>
                    <group>
                        <field name="phone" widget="phone"/>
                    </group>
                </sheet>
            </form>`,
    });
});

test("Mobile: cannot call and how_to_call_on_mobile='phone' does not show softphone.", async () => {
    patchWithCleanup(Voip.prototype, {
        get canCall() {
            return false;
        },
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+1 234 567 890" });
    pyEnv["res.users.settings"].create({
        how_to_call_on_mobile: "phone",
        user_id: serverState.userId,
    });
    await start();
    await openFormView("fake", fakeId);

    await click(".o_field_phone .o_phone_form_link");
    // Softphone should NOT be shown (falls back to native dialer)
    await contains(".o-voip-Softphone", { count: 0 });
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+1 234 567 890"]])).toBe(0);
    expect.verifySteps(["tel:+1234567890"]);
});

test("Mobile: cannot call and how_to_call_on_mobile='ask' with Phone selection falls back to native dialer.", async () => {
    patchWithCleanup(Voip.prototype, {
        get canCall() {
            return false;
        },
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+1 234 567 890" });
    pyEnv["res.users.settings"].create({
        how_to_call_on_mobile: "ask",
        user_id: serverState.userId,
    });
    await start();
    await openFormView("fake", fakeId);

    await click(".o_field_phone .o_phone_form_link");
    await click("label[for='phone']");
    await click(".modal-dialog .btn-primary");
    // Softphone should NOT be shown
    await contains(".o-voip-Softphone", { count: 0 });
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+1 234 567 890"]])).toBe(0);
    expect.verifySteps(["tel:+1234567890"]);
});
