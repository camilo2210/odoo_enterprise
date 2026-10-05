import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { mockUserAgent, tick } from "@odoo/hoot-mock";
import {
    click,
    contains,
    openFormView,
    registerArchs,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Fake } from "@voip/../tests/mock_server/mock_models/fake";
import {
    defineModels,
    getMockEnv,
    getService,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { callPhoneNumber } from "@web/core/phone/phone_call";

describe.current.tags("desktop");
setupVoipTests();
defineModels({ Fake });

beforeEach(() => {
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

test("VoIP phone call handler preserves the makeCall return value", async () => {
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip.userAgent, {
        makeCall() {
            return false;
        },
    });

    const callMade = await callPhoneNumber(getMockEnv(), { phoneNumber: "+1 202 555 0182" });

    expect(callMade).toBe(false);
});

test("VoIP phone input displays selectable formatted text without a call button", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({
        phone: "6504193846",
        phone_formatted: "+1 650-419-3846",
    });
    registerArchs({
        "fake,false,form": `
            <form string="Fake">
                <field name="phone_formatted" invisible="1"/>
                <field name="phone" widget="voip_phone_input"/>
            </form>`,
    });
    await start();
    await openFormView("fake", fakeId);

    const input = document.querySelector(".o_field_widget[name='phone'] input");
    expect(input).toHaveValue("+1 650-419-3846");
    input.setSelectionRange(3, 6);
    expect(input.value.slice(input.selectionStart, input.selectionEnd)).toBe("650");
    expect(".o_field_widget[name='phone'] .o_phone_form_link").toHaveCount(0);
});

test("Phone call handler ignores clicks while a call is pending and cleans up afterwards", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+1 202 555 0182" });
    const firstCall = Promise.withResolvers();
    await start();
    const voip = await getService("voip");
    let makeCallCount = 0;
    patchWithCleanup(voip.userAgent, {
        makeCall() {
            makeCallCount++;
            expect.step("makeCall");
            return makeCallCount === 1 ? firstCall.promise : true;
        },
    });
    await openFormView("fake", fakeId);

    await click(".o_field_phone .o_phone_form_link");
    await click(".o_field_phone .o_phone_form_link");

    expect.verifySteps(["makeCall"]);
    firstCall.resolve(true);
    await tick();
    await click(".o_field_phone .o_phone_form_link");
    expect.verifySteps(["makeCall"]);
});

test("Click on PhoneField link triggers a call and creates a call activity", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+36 55 369 678" });
    await start();
    await openFormView("fake", fakeId);

    expect(".o_field_phone .o_phone_form_link").toHaveAttribute("href", "tel:+3655369678");
    await click(".o_field_phone .o_phone_form_link");
    await contains(".o-voip-InCallView");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+36 55 369 678"]])).toBe(1);
    // The Log button should not appear in the InCallView since activity_id is set on the call
    await contains(".o-voip-InCallView .o-voip-ActionButton-icon[data-icon='schedule']", {
        count: 0,
    });
});

test("An unavailable desktop call uses the native phone link without creating a call", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+36 55 369 678" });
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip, {
        get canCall() {
            return false;
        },
    });
    await openFormView("fake", fakeId);
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });

    await click(".o_field_phone .o_phone_form_link");

    expect.verifySteps(["tel:+3655369678"]);
    await contains(".o-voip-Softphone", { count: 0 });
    expect(pyEnv["voip.call"].search_count([])).toBe(0);
});

test("An external Odoo call without an outbound number uses the native phone link", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+36 55 369 678" });
    onRpc("voip.call", "resolve_outgoing_dial_number", () => ({
        number: "+3655369678",
        is_internal: false,
    }));
    await start();
    const voip = await getService("voip");
    voip.config = {
        ...voip.config,
        usesOdooProvider: true,
        mode: "prod",
        outboundCallerId: null,
    };
    patchWithCleanup(voip, {
        get canCall() {
            return true;
        },
    });
    patchWithCleanup(voip.userAgent.notification, {
        add() {
            expect.step("warning");
        },
    });
    await openFormView("fake", fakeId);
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });

    await click(".o_field_phone .o_phone_form_link");
    await tick();

    await contains(".o-voip-Softphone", { count: 0 });
    expect(pyEnv["voip.call"].search_count([])).toBe(0);
    expect.verifySteps(["tel:+3655369678"]);
});

test("An unavailable VoIP call on a mobile OS uses the native phone link", async () => {
    mockUserAgent("android");
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+36 55 369 678" });
    pyEnv["res.users.settings"].create({
        how_to_call_on_mobile: "voip",
        user_id: serverState.userId,
    });
    await start();
    const voip = await getService("voip");
    patchWithCleanup(voip, {
        get canCall() {
            return false;
        },
    });
    await openFormView("fake", fakeId);
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });

    await click(".o_field_phone .o_phone_form_link");

    expect.verifySteps(["tel:+3655369678"]);
    await contains(".o-voip-Softphone", { count: 0 });
});

test("Click on PhoneField link in readonly form view does not switch the form view to edit mode.", async () => {
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({ phone: "+689 312172" });
    await start();
    await openFormView("fake", fakeId);
    await click(".o_field_phone .o_phone_form_link");
    await tick();
    await contains(".o_form_readonly");
});

test("PhoneField displays formatted value and dials the per-field sanitized (E164) number.", async () => {
    registerArchs({
        "fake,false,form": `
            <form string="Fake" edit="0">
                <sheet>
                    <group>
                        <field name="phone_sanitized" invisible="1"/>
                        <field name="phone_formatted" invisible="1"/>
                        <field name="phone" widget="phone"/>
                    </group>
                </sheet>
            </form>`,
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({
        phone: "0612345678",
        phone_sanitized: "+33612345678",
        phone_formatted: "+33 6 12 34 56 78",
    });
    await start();
    await openFormView("fake", fakeId);
    await contains(".o_field_phone span", { text: "+33 6 12 34 56 78" });
    await click(".o_field_phone .o_phone_form_link");
    await contains(".o-voip-InCallView");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+33612345678"]])).toBe(1);
});

test("PhoneField falls back to raw value when formatted field is empty.", async () => {
    registerArchs({
        "fake,false,form": `
            <form string="Fake" edit="0">
                <sheet>
                    <group>
                        <field name="phone_sanitized" invisible="1"/>
                        <field name="phone_formatted" invisible="1"/>
                        <field name="phone" widget="phone"/>
                    </group>
                </sheet>
            </form>`,
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({
        phone: "0612345678",
        phone_sanitized: false,
        phone_formatted: false,
    });
    await start();
    await openFormView("fake", fakeId);
    await contains(".o_field_phone span", { text: "0612345678" });
    await click(".o_field_phone .o_phone_form_link");
    await contains(".o-voip-InCallView");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "0612345678"]])).toBe(1);
});

test("Two PhoneField widgets on the same record dial each their own sanitized counterpart.", async () => {
    registerArchs({
        "fake,false,form": `
            <form string="Fake" edit="0">
                <sheet>
                    <group>
                        <field name="phone_sanitized" invisible="1"/>
                        <field name="phone_formatted" invisible="1"/>
                        <field name="mobile_sanitized" invisible="1"/>
                        <field name="mobile_formatted" invisible="1"/>
                        <field name="phone" widget="phone"/>
                        <field name="mobile" widget="phone"/>
                    </group>
                </sheet>
            </form>`,
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({
        phone: "0611111111",
        phone_sanitized: "+33611111111",
        phone_formatted: "+33 6 11 11 11 11",
        mobile: "0622222222",
        mobile_sanitized: "+33622222222",
        mobile_formatted: "+33 6 22 22 22 22",
    });
    await start();
    await openFormView("fake", fakeId);
    const links = queryAll(".o_field_phone .o_phone_form_link");
    await click(links[0]);
    await click(links[1]);
    await contains(".o-voip-CallBanner"); // Wait for both calls to be initiated
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+33611111111"]])).toBe(1);
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+33622222222"]])).toBe(1);
});

test("Mobile widget does not fall back to phone_sanitized when mobile_sanitized is missing.", async () => {
    registerArchs({
        "fake,false,form": `
            <form string="Fake" edit="0">
                <sheet>
                    <group>
                        <field name="phone_sanitized" invisible="1"/>
                        <field name="phone_formatted" invisible="1"/>
                        <field name="mobile_sanitized" invisible="1"/>
                        <field name="mobile_formatted" invisible="1"/>
                        <field name="phone" widget="phone"/>
                        <field name="mobile" widget="phone"/>
                    </group>
                </sheet>
            </form>`,
    });
    const pyEnv = await startServer();
    const fakeId = pyEnv["fake"].create({
        phone: "0611111111",
        phone_sanitized: "+33611111111",
        phone_formatted: "+33 6 11 11 11 11",
        mobile: "0622222222",
        mobile_sanitized: false,
        mobile_formatted: false,
    });
    await start();
    await openFormView("fake", fakeId);
    const links = queryAll(".o_field_phone .o_phone_form_link");
    await click(links[1]);
    await contains(".o-voip-InCallView");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "0622222222"]])).toBe(1);
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "+33611111111"]])).toBe(0);
});
