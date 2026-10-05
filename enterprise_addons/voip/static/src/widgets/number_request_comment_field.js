import { registry } from "@web/core/registry";
import { TextField, textField } from "@web/views/fields/text/text_field";

import { useListener } from "@odoo/owl";

export class NumberRequestCommentField extends TextField {
    setup() {
        super.setup();
        useListener(this.textareaRef, "input", (ev) => {
            this.props.record.update({ [this.props.name]: this.parse(ev.target.value) });
        });
    }
}

registry.category("fields").add("voip_number_request_comment", {
    ...textField,
    component: NumberRequestCommentField,
});
