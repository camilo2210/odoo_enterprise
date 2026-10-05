import { charField, CharField } from "@web/views/fields/char/char_field";
import { registry } from "@web/core/registry";
import { useAutoresize } from "@web/core/utils/autoresize";

export class AutoSizeCharField extends CharField {
    setup() {
        super.setup();
        useAutoresize(this.input);
    }
}

const autosizeCharField = {
    ...charField,
    component: AutoSizeCharField,
};

registry.category("fields").add("autosize_char", autosizeCharField);
