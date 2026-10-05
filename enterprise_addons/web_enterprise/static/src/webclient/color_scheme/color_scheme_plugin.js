import { registry } from "@web/core/registry";
import { location, browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";
import { user } from "@web/core/user";
import { computed, onWillStart, Plugin, usePlugin } from "@odoo/owl";
import { services } from "@web/core/services";

export class ColorSchemePlugin extends Plugin {
    colorScheme = computed(() => {
        let colorScheme = browser.matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light";
        if (["light", "dark"].includes(user.settings.color_scheme)) {
            colorScheme = user.settings.color_scheme;
        }
        return colorScheme;
    });

    setup() {
        let colorScheme = this.colorScheme();
        const current = cookie.get("color_scheme");
        if (colorScheme !== current) {
            cookie.set("color_scheme", colorScheme);
            if (current || (!current && colorScheme === "dark")) {
                location.reload();
                onWillStart(() => new Promise(() => {})); // block WebClient rendering to avoid flickering
            }
        }
    }
}

services.add(ColorSchemePlugin);

/**
 * -----------------------------------------------------------------------------
 * @todo owl3 migration
 * temporary - to remove when all use of the color_scheme service are removed
 * -----------------------------------------------------------------------------
 */
registry.category("services").add("color_scheme", {
    start() {
        return usePlugin(ColorSchemePlugin);
    },
});
