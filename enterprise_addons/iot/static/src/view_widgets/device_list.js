import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class DeviceListField extends X2ManyField {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
    }

    /**
     * By default the `X2ManyField` opens records in a dialog,
     * however this dialog doesn't run the `js_class` Controller
     * which is responsible for saving fields to the IoT box.
     *
     * We override the behaviour to open the regular form view
     * for the device, working around the issue.
     * @override
     */
    async openRecord(record, options = {}) {
        return this.switchToForm(record, options);
    }
}

export const deviceListField = {
    ...x2ManyField,
    component: DeviceListField,
};

registry.category("fields").add("device_list_field", deviceListField);
