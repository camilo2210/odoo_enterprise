import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

const viewRegistry = registry.category("views");

export class PaidTimeOffFormController extends FormController {
    get modelParams() {
        const params = super.modelParams;
        params.hooks.onRecordChanged = (record) => {
            record.save();
        };
        return params;
    }
}

export const paidTimeOffFormView = {
    ...formView,
    Controller: PaidTimeOffFormController,
};

viewRegistry.add("paid_time_off_form", paidTimeOffFormView);
