import { Component, proxy, signal, t, useProps } from "@odoo/owl";

import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * Country selector dropdown items.
 * Allows selecting a country to set the phone number prefix.
 */
export class CountrySelectorItems extends Component {
    static components = { DropdownItem };
    static template = "voip.CountrySelectorItems";

    props = useProps({
        onCountrySelected: t.function(),
    });

    countryFilterInputRef = signal.ref();

    setup() {
        this.voip = useService("voip");
        this.state = proxy({ input: "" });
    }

    get filteredCountries() {
        const countries = [...this.voip.store["res.country"].records.values()];
        const filter = this.state.input.toLowerCase();
        if (!filter) {
            return countries;
        }
        const matchesByIso = [];
        const matchesByName = [];
        const matchesByCode = [];
        for (const country of countries) {
            const iso = country.code.toLowerCase();
            const name = country.name.toLowerCase();
            const code = String(country.phone_code);
            if (iso.includes(filter)) {
                matchesByIso.push(country);
            } else if (name.includes(filter)) {
                matchesByName.push(country);
            } else if (filter.startsWith("+") && code.startsWith(filter.slice(1))) {
                matchesByCode.push(country);
            } else if (filter.startsWith("00") && code.startsWith(filter.slice(2))) {
                matchesByCode.push(country);
            } else if (code.includes(filter)) {
                matchesByCode.push(country);
            }
        }
        return [...matchesByIso, ...matchesByName, ...matchesByCode];
    }

    flagAltLabel(country) {
        if (!country) {
            return "";
        }
        return _t("%(country)s (+%(phone_prefix)s)", {
            country: country.code,
            phone_prefix: country.phone_code,
        });
    }
}
