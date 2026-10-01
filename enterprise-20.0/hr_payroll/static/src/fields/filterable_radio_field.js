import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { RadioField, radioField, radioFieldProps } from "@web/views/fields/radio/radio_field";
import { useProps, t } from "@odoo/owl";

export class FilterableRadioField extends RadioField {
    props = useProps({
        ...radioFieldProps,
        whitelist_fname: t.string().optional(),
        whitelisted_values: t.array().optional(),
        blacklisted_values: t.array().optional(),
    });

    /**
     * @override
     */
    get items() {
        let items = super.items;
        if (this.type === "selection") {
            if (this.props.whitelist_fname) {
                items = items.filter((item) =>
                    this.props.record.data[this.props.whitelist_fname].includes(item[0])
                );
            } else if (this.props.whitelisted_values) {
                items = items.filter((item) => this.props.whitelisted_values.includes(item[0]));
            } else if (this.props.blacklisted_values) {
                items = items.filter((item) => !this.props.blacklisted_values.includes(item[0]));
            }
        }
        return items;
    }
}

export const filterableRadioField = {
    ...radioField,
    component: FilterableRadioField,
    additionalClasses: ["o_field_radio"],
    supportedOptions: [
        {
            label: _t("Whitelisted Values"),
            name: "whitelisted_values",
            type: "string",
        },
        {
            label: _t("Blacklisted Values"),
            name: "blacklisted_values",
            type: "string",
        },
        {
            label: _t("Whitelisted field name"),
            name: "whitelist_fname",
            type: "string",
        },
    ],
    extractProps: ({ options, string }, dynamicInfo) => ({
        ...radioField.extractProps({ options, string }, dynamicInfo),
        whitelist_fname: options.whitelist_fname,
        whitelisted_values: options.whitelisted_values,
        blacklisted_values: options.blacklisted_values,
    }),
};

registry.category("fields").add("filterable_radio", filterableRadioField);
