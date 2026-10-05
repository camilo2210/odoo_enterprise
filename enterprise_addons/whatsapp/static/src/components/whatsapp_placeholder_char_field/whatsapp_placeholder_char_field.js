import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";


export class WhatsappPlaceholderCharField extends CharField {
    static template = "whatsapp.WhatsappPlaceholderCharField";
    setup() {
        super.setup();
        this.placeholders = proxy(this.env.placeholders || {});
    }
}

export const whatsappPlaceholderCharField = {
    ...charField,
    component: WhatsappPlaceholderCharField,
};

registry.category("fields").add("whatsapp_placeholder_char", whatsappPlaceholderCharField);
