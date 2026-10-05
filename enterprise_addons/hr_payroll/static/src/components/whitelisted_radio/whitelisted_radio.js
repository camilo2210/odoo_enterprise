/** @odoo-module **/

import { registry } from "@web/core/registry";
import { radioField, RadioField, radioFieldProps } from "@web/views/fields/radio/radio_field";
import { useProps, t, useEffect } from "@odoo/owl";


/**
 * The extension of radio field that can take whitelisted values and only those values will be shown in the selection
 */

export class WhitelistedRadioField extends RadioField {

    props = useProps({
        ...radioFieldProps,
        whitelisted_values: t.array().optional(),
    });

    setup(){
        super.setup();
        useEffect(() => {
            // Only set a default if the field is currently unset 
            // OR if the current value is not in our whitelist
            const currentValue = this.props.record.data[this.props.name];
            const validItems = this.items.map(i => i[0]);

            if (!currentValue || !validItems.includes(currentValue)) {
                this.props.record.update({ [this.props.name]: validItems[0] });
            }
        });
    }

    /**
     * @override
     */

    get items() {
        const allItems = super.items;
        
        const whitelisted_values = this.props.whitelisted_values || [];

        if (whitelisted_values.length > 0) {
            return allItems.filter(item => whitelisted_values.includes(item[0]));
        }
        
        return allItems;
    }
}

export const whitelistedRadioField = {
    ...radioField, 
    component: WhitelistedRadioField,
    supportedOptions: [
        {
            label: "Whitelisted Values",
            name: "whitelisted_values",
            type: "string"
        }
    ],
    extractProps({ options }) {
        const props = radioField.extractProps(...arguments);
        props.whitelisted_values = options.whitelisted_values;
        return props;
    },
}


registry.category("fields").add("whitelisted_radio", whitelistedRadioField);
