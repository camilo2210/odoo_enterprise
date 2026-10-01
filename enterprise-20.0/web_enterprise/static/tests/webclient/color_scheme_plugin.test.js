import { animationFrame, expect, mockMatchMedia, test } from "@odoo/hoot";
import {
    defineModels,
    fields,
    mountWithCleanup,
    patchWithCleanup,
    webModels,
} from "@web/../tests/web_test_helpers";
import { location } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { _makeUser, user } from "@web/core/user";

class ResUsersSettings extends webModels.ResUsersSettings {
    color_scheme = fields.Selection({
        selection: [
            ["system", "System"],
            ["light", "Light"],
            ["dark", "Dark"],
        ],
        default: "system",
    });

    _records = [
        {
            id: 1,
            color_scheme: "system",
        },
    ];
}

defineModels([ResUsersSettings]);

test("use 'system' color scheme (light)", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "light" });
    patchWithCleanup(location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "system" } }));
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("light");
    expect.verifySteps([]);
});

test("use 'system' color scheme (dark)", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "dark" });
    patchWithCleanup(location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "system" } }));
    // The plugin blocks rendering forever (onWillStart never resolves) to avoid
    // flickering until the real page reload kicks in, so don't await the mount.
    mountWithCleanup(MainComponentsContainer);
    await animationFrame();
    expect(cookie.get("color_scheme")).toBe("dark");
    expect.verifySteps(["reloadPage"]);
    expect(".o-main-components-container").toHaveCount(0);
});

test("use 'light' color scheme", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "dark" });
    patchWithCleanup(location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "light" } }));
    ResUsersSettings._records[0].color_scheme = "light";
    await mountWithCleanup(MainComponentsContainer);
    expect(cookie.get("color_scheme")).toBe("light");
    expect.verifySteps([]);
});

test("use 'dark' color scheme", async () => {
    mockMatchMedia({ ["prefers-color-scheme"]: "light" });
    patchWithCleanup(location, {
        reload: () => expect.step("reloadPage"),
    });
    patchWithCleanup(user, _makeUser({ user_settings: { id: 1, color_scheme: "dark" } }));
    ResUsersSettings._records[0].color_scheme = "dark";
    // The plugin blocks rendering forever (onWillStart never resolves) to avoid
    // flickering until the real page reload kicks in, so don't await the mount.
    mountWithCleanup(MainComponentsContainer);
    await animationFrame();
    expect(cookie.get("color_scheme")).toBe("dark");
    expect.verifySteps(["reloadPage"]);
    expect(".o-main-components-container").toHaveCount(0);
});
