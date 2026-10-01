import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click } from "@odoo/hoot-dom";
import { animationFrame, mockUserAgent } from "@odoo/hoot-mock";
import {
    defineModels,
    fields,
    getMockEnv,
    mockService,
    models,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { browser } from "@web/core/browser/browser";
import { callPhoneNumber } from "@web/core/phone/phone_call";
import { user } from "@web/core/user";

class Partner extends models.Model {
    phone = fields.Char();

    _records = [{ id: 1, phone: "+32 87 00 00 11" }];
}

defineModels([Partner]);
describe.current.tags("desktop");

beforeEach(() => {
    patchWithCleanup(user, { isSystem: true });
});

async function mountPhoneField() {
    await mountView({
        type: "form",
        resModel: "partner",
        resId: 1,
        readonly: true,
        arch: /* xml */ `
            <form>
                <field name="phone" widget="phone"/>
            </form>`,
    });
    patchWithCleanup(getMockEnv().services, { voip: undefined });
}

test("system users are offered to install Odoo Phone on desktop", async () => {
    await mountPhoneField();

    expect(".o_field_phone .o_phone_form_link").toHaveAttribute("href", "tel:+3287000011");
    await click(".o_field_phone .o_phone_form_link");
    await animationFrame();
    expect(".modal-title").toHaveText("");
    expect(".o_phone_install_dialog_heading").toHaveText("Make and receive calls right from Odoo");
    expect(".modal-dialog").toHaveClass("modal-xl");
    expect(".o_phone_install_dialog_promo").toHaveCount(1);
    expect(".o_phone_install_dialog_screenshot").toHaveCount(2);
    expect(".modal-footer").toHaveCount(0);
    expect(".modal .btn-primary").toHaveText("Install App");
    expect(".modal .o_phone_install_dialog_video").toHaveText("Watch Video");
    expect(".modal .o_phone_install_dialog_video").toHaveAttribute(
        "href",
        "https://youtu.be/sDZErem-PME"
    );
    expect(".modal .o_phone_install_dialog_video").toHaveAttribute("target", "_blank");
    expect(".modal .o_phone_install_dialog_video").toHaveAttribute("rel", "noopener noreferrer");

    await click(".modal .btn-close");
    await animationFrame();
    expect(".modal").toHaveCount(0);
    await click(".o_field_phone .o_phone_form_link");
    await animationFrame();
    expect(".modal-title").toHaveText("");
});

test("opening the Odoo Phone installation dialog does not report a call", async () => {
    await mountPhoneField();

    const callMade = callPhoneNumber(getMockEnv(), { phoneNumber: "+32 87 00 00 11" });

    expect(callMade).toBe(false);
    await animationFrame();
    expect(".o_phone_install_dialog_promo").toHaveCount(1);
});

test("installing Odoo Phone follows the action returned by the module installation", async () => {
    const nextAction = {
        type: "ir.actions.act_url",
        target: "self",
        url: "/odoo/action-voip.action_voip_did_number_search_wizard",
    };
    onRpc("search_read", ({ model }) => {
        if (model === "ir.module.module") {
            expect.step("find voip");
            return [{ id: 42 }];
        }
    });
    onRpc("button_immediate_install", ({ args, model }) => {
        if (model === "ir.module.module") {
            expect(args[0]).toEqual([42]);
            expect.step("install voip");
            return nextAction;
        }
    });
    mockService("action", {
        async doAction(action) {
            expect(action).toEqual(nextAction);
            expect.step("open buy wizard");
        },
    });
    await mountPhoneField();

    await click(".o_field_phone .o_phone_form_link");
    await animationFrame();
    await click(".modal .btn-primary");
    await animationFrame();

    expect.verifySteps(["find voip", "install voip", "open buy wizard"]);
});

test("regular users keep the native phone link", async () => {
    patchWithCleanup(user, { isSystem: false });
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
    await mountPhoneField();

    await click(".o_field_phone .o_phone_form_link");

    expect.verifySteps(["tel:+3287000011"]);
    expect(".modal").toHaveCount(0);
});

test("system users on a mobile OS keep the native phone link", async () => {
    mockUserAgent("android");
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
    await mountPhoneField();

    await click(".o_field_phone .o_phone_form_link");

    expect.verifySteps(["tel:+3287000011"]);
    expect(".modal").toHaveCount(0);
});
