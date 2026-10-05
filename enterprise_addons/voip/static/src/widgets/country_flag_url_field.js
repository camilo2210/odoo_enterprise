import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { ImageUrlField, imageUrlField } from "@web/views/fields/image_url/image_url_field";

export class CountryFlagUrlField extends ImageUrlField {
    static template = "voip.CountryFlagUrlField";

    /**
     * Gets the accessible alternative text for the country flag.
     * Uses the display name of the country if available.
     * @returns {string} The localized alt text (e.g., "China flag") or an empty string.
     */
    get altText() {
        const country = this.props.record.data.country_id?.display_name;
        return country ? _t("%(country)s flag", { country }) : "";
    }

    /**
     * Gets the display name of the country for the tooltip.
     * @returns {string} The country's display name, or an empty string if not available.
     */
    get tooltip() {
        return this.props.record.data.country_id?.display_name ?? "";
    }
}

export const countryFlagUrlField = {
    ...imageUrlField,
    component: CountryFlagUrlField,
    displayName: _t("Country Flag"),
    fieldDependencies: [
        { name: "country_id", type: "many2one" },
    ],
};

registry.category("fields").add("country_flag_url", countryFlagUrlField);
