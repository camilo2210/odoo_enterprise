import { describe, expect, test } from "@odoo/hoot";
import { tick } from "@odoo/hoot-mock";
import {
    click,
    contains,
    openFormView,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { browser } from "@web/core/browser/browser";
import { getService, patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Click on Call from activity info triggers a call.", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["mail.activity"].create({
        phone: "+1 202-555-0182",
        res_id: partnerId,
        res_model: "res.partner",
    });
    await start();
    await openFormView("res.partner", partnerId);
    await contains(".o-mail-Activity-phoneNumber", { text: "+1 202-555-0182" });
    await click(".o-mail-Activity-call[href='tel:+12025550182']");
    await tick();
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+1 202-555-0182"]])).toBe(1);
});

test("An unavailable call activity uses the native dialer.", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({});
    pyEnv["mail.activity"].create({
        phone: "+1-202-555-0182",
        res_id: partnerId,
        res_model: "res.partner",
    });
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip, {
        get canCall() {
            return false;
        },
    });
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
    await openFormView("res.partner", partnerId);

    await click(".o-mail-Activity-call");

    expect.verifySteps(["tel:+12025550182"]);
    expect(pyEnv["voip.call"].search_count([])).toBe(0);
});
