import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController, formControllerProps } from "@web/views/form/form_controller";
import { useProps, t } from "@odoo/owl";

class AppointmentInsertLinkFormController extends FormController {
    props = useProps({
        ...formControllerProps,
        insertLink: t.function(),
        closeDialog: t.function(),
    });
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.special) {
            if (clickParams.special === "save") { // Insert Link button
                const saved = await this.model.root.save();
                if (saved) {
                    this.props.insertLink(this.model.root.data.book_url);
                } else {
                    return false;
                }
            }
            this.props.closeDialog();
            return false;
        }
        return super.beforeExecuteActionButton(...arguments);
    }
}
registry.category("views").add("appointment_insert_link_form", {
    ...formView,
    Controller: AppointmentInsertLinkFormController,
});
