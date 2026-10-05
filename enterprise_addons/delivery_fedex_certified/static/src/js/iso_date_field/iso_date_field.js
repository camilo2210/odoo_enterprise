/** @odoo-module **/
import {DateTimeField, dateField} from '@web/views/fields/datetime/datetime_field'
import {formatDate} from "@web/core/l10n/dates";
import {registry} from "@web/core/registry";
import {xml} from "@odoo/owl"

export class IsoDateField extends DateTimeField {
    static template = xml`
        <p
            class="o_input"
            t-ref="this.startDateRef"
            t-if="this.value"
            t-out="this.value"
        />
        <input class="o_input" style="border: none; outline: none" t-ref="this.startDateRef" t-else=""/>
    `;

    get value() {
        return formatDate(this.state.value, {format: 'yyyy-MM-dd'})
    }
}

registry.category("fields").add("iso_date_field", {...dateField, component: IsoDateField});
