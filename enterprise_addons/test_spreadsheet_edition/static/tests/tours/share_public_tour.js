import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_spreadsheet_edition.spreadsheet_command_whitelist", {
    steps: () => [
        {
            trigger: ".o_web_client",
            run: async () => {
                await loadBundle("spreadsheet.o_spreadsheet");
                const { coreTypes } = odoo.loader.modules.get("@odoo/o-spreadsheet");
                const result = await browser.fetch("/test/spreadsheet/public_command_permissions");
                const missing = coreTypes.difference(new Set(await result.json()));
                if (missing.size > 0) {
                    const msg = `The following core types are not in the public command permissions list.\nDid you forget to add the command to PUBLIC_COMMAND_PERMISSIONS?:\n${[...missing].join("\n")}`;
                    throw new Error(msg);
                }
            },
        },
    ],
});
