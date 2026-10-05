import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";

export class POSAppointmentQuickCreateFormController extends FormController {
    getButtonClass(status) {
        let buttonClass = "btn-secondary";
        const { data } = this.model.root;
        if (data.appointment_status === status) {
            const colorIndex = {
                attended: 10,
                booked: luxon.DateTime.now().diff(data.start, ["minutes"]).minutes > 15 ? 2 : 4,
                no_show: 1,
            }[status];
            buttonClass = `o_appointment_status_btn_color_${colorIndex}`;
        }
        return buttonClass;
    }

    onClickAppointmentStatus(status) {
        this.model.root.update({ appointment_status: status });
        this.saveButtonClicked();
    }
}

registry.category("views").add("pos_appointment_quick_create_form_view", {
    ...formView,
    Controller: POSAppointmentQuickCreateFormController,
});
