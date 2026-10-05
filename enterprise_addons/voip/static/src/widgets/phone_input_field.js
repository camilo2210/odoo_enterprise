import { registry } from "@web/core/registry";
import { phoneField } from "@web/views/fields/phone/phone_field";

// TODO remove in master (there is now a dedicated display_buttons option in the
// base phone widget).
registry.category("fields").add("voip_phone_input", {
    ...phoneField,
    extractProps: (fieldInfo) => ({
        ...phoneField.extractProps(fieldInfo),
        displayButtons: false,
    }),
});
