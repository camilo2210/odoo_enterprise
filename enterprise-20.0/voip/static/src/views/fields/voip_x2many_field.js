import { VoipResultLineListRenderer } from "@voip/views/list/list_renderer";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class VoipX2ManyResultLineField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: VoipResultLineListRenderer,
    };
}

export const voipX2ManyResultLineField = {
    ...x2ManyField,
    component: VoipX2ManyResultLineField,
};

registry.category("fields").add("voip_x2many_result_line_ids", voipX2ManyResultLineField);
