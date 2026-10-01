import { BurgerMenuDialog } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { cookie } from "@web/core/browser/cookie";
import { location } from "@web/core/browser/browser";
import { getColorScheme } from "@point_of_sale/utils";
import { _t } from "@web/core/l10n/translation";

const colorSchemePatch = {
    get colorScheme() {
        return getColorScheme();
    },
    get colorSchemeLabel() {
        return this.colorScheme === "dark" ? _t("Switch to Light Mode") : _t("Switch to Dark Mode");
    },
    toggleColorScheme() {
        cookie.set("pos_color_scheme", this.colorScheme === "dark" ? "light" : "dark");
        location.reload();
    },
};

patch(BurgerMenuDialog.prototype, colorSchemePatch);
