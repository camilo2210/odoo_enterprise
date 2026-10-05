import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, t, useProps } from "@odoo/owl";

export class FlagPhoneField extends Component {
    static template = "voip.FlagPhoneField";

    props = useProps({
        ...standardFieldProps,
        height: t.number().optional(),
        width: t.number().optional(),
    });

    setup() {
        this.regionNames = new Intl.DisplayNames(user.lang, { type: "region" });
    }

    /**
     * Gets the display name of the country for the tooltip.
     * @returns {string} The country's display name, or an empty string if not available.
     */
    get tooltip() {
        return this.props.record.data.country_id?.display_name ?? "";
    }

    /**
     * Gets the alternative text for the country flag image.
     * @returns {string} A localized string containing the country name (e.g., "China flag"),
     * or an empty string if the country data is missing.
     */
    get imgAlt() {
        if (this.props.record.data.country_id) {
            return _t("%(country)s flag", {
                country: this.props.record.data.country_id.display_name,
            });
        }
        return "";
    }

    get height() {
        return this.props.height;
    }

    get width() {
        return this.props.width;
    }
}

export const flagPhoneField = {
    component: FlagPhoneField,
    displayName: "Flag Phone",
    supportedTypes: ["char", "text"],
    fieldDependencies: [{ name: "country_id", type: "many2one" }],
    extractProps: () => ({
        height: 20,
        width: 20,
    }),
};

registry.category("fields").add("voip_flag_phone", flagPhoneField);
