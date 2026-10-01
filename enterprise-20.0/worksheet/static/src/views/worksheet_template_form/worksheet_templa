import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

export const worksheetTemplateDeleteConfirmationMessage = _t(
    "Deleting this template will also delete the related worksheets.\n\nAre you sure you want to proceed?"
);

export class WorksheetTemplateFormController extends FormController {
    setup() {
        super.setup();
        this.propertiesState.editable = true;
    }

    get deleteConfirmationDialogProps() {
        const deleteConfirmationDialogProps = super.deleteConfirmationDialogProps;
        if (this.model.root.data.worksheet_count) {
            deleteConfirmationDialogProps.body = worksheetTemplateDeleteConfirmationMessage;
        }
        return deleteConfirmationDialogProps;
    }
}

export const worksheetTemplateFormView = {
    ...formView,
    Controller: WorksheetTemplateFormController,
};

registry.category("views").add("worksheet_template_form", worksheetTemplateFormView);
