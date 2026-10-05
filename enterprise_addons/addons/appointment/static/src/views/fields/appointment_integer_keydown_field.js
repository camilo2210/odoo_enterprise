import { useListener } from "@odoo/owl";

import { registry } from "@web/core/registry";
import { useDebounced } from "@web/core/utils/timing";
import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";
import { parseInteger } from "@web/views/fields/parsers";


export class AppointmentIntegerKeydownField extends IntegerField {
    setup() {
        super.setup(...arguments);
        // we want this to be fairly quick so users can see the change almost immediately
        // after typing it, but we still want common fast cases to only trigger once
        const triggerOnChange = useDebounced(this.triggerOnChange.bind(this), 200);
        useListener(this.numpadDecimalRef, "keydown", triggerOnChange);
    }

    triggerOnChange() {
        const input = this.numpadDecimalRef();
        // don't trigger change on invalid as it would reset to 0 immediately
        try {
            parseInteger(input.value, { allowOperation: true });
        } catch {
            return;
        }
        input.dispatchEvent(new Event("change"));
    }
}

export const integerKeydownField = {
    ...integerField,
    component: AppointmentIntegerKeydownField,
};

registry.category("fields").add("appointment_integer_keydown", integerKeydownField);
