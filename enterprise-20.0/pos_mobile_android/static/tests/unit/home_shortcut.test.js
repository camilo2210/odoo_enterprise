import { expect, test } from "@odoo/hoot";
import { mockFetch } from "@odoo/hoot-mock";
import { browser } from "@web/core/browser/browser";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import mobile from "@web_mobile/js/services/core";
import {
    addPosHomeShortcut,
    canAddHomeShortcut,
} from "@pos_mobile_android/app/utils/home_shortcut";

const config = { id: 3, display_name: "Shop counter" };

test("outside the mobile app there is no shortcut to offer", () => {
    expect(canAddHomeShortcut()).toBe(false);
});

test("the shortcut opens this point of sale, under its name and icon", async () => {
    mockFetch(() => "PNG");
    patchWithCleanup(mobile.methods, {
        addHomeShortcut: async (args) => {
            expect.step(args);
            return { success: true, data: true };
        },
    });

    expect(canAddHomeShortcut()).toBe(true);
    await addPosHomeShortcut(config);

    expect.verifySteps([
        {
            title: "Shop counter",
            shortcut_url: `${browser.location.origin}/pos/ui/3`,
            web_icon: "UE5H",
        },
    ]);
});

test("an icon that cannot be read leaves the app's own", async () => {
    mockFetch(() => {
        throw new Error("offline");
    });
    patchWithCleanup(mobile.methods, {
        addHomeShortcut: async ({ web_icon }) => {
            expect.step(`icon: "${web_icon}"`);
            return { success: true, data: true };
        },
    });

    await addPosHomeShortcut(config);

    expect.verifySteps([`icon: ""`]);
});
