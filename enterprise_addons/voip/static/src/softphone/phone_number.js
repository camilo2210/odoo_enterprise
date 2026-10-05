import { Component, useProps, t } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";

/**
 * Rendering a phone number alongside its corresponding country flag.
 */
export class PhoneNumber extends Component {
    props = useProps({
        number: t.string(),
        country: t.or([t.object(), t.literal(null)]).optional(null),
    });
    static template = "voip.PhoneNumber";

    /**
     * Gets the alternative text for the flag icon.
     * @returns {string} The localized country flag description (e.g., "China flag")
     * or an empty string if the country name is not provided.
     */
    get flagAlt() {
        return this.props.country?.name
            ? _t("%(country)s flag", { country: this.props.country.name })
            : "";
    }

    /**
     * Gets the country name for the flag tooltip.
     * @returns {string} The name of the country, or an empty string if not available.
     */
    get flagTooltip() {
        return this.props.country?.name ?? "";
    }

    /**
     * Gets the URL of the country flag image.
     * @returns {string|null} The flag image URL, or null if the URL is not available.
     */
    get flagUrl() {
        return this.props.country?.image_url ?? null;
    }
}
