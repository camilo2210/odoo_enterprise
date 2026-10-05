import { registry } from "@web/core/registry";
import { serializeDate } from "@web/core/l10n/dates";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";

/**
 * When the user clicks the "Duplicate" cog menu item, the system opens the audit
 * report form view. When the user clicks the "Duplicate" button, the following
 * controller creates a new audit report using the current form values, discards
 * any unsaved changes, closes the modal, and refreshes the parent view.
 */
export class AuditReportFormController extends FormController {
    /** @override */
    async beforeExecuteActionButton(clickParams) {
        if (clickParams.name === "duplicate_audit_report") {
            const values = {
                title: this.model.root.data.title,
                responsible_user_ids: this.model.root.data.responsible_user_ids._currentIds,
            };
            if (this.model.root.data.start_date) {
                values.start_date = serializeDate(this.model.root.data.start_date);
            }
            if (this.model.root.data.end_date) {
                values.end_date = serializeDate(this.model.root.data.end_date);
            }
            await this.env.services.orm.call("audit.report", "copy_audit_report", [this.props.context.original_audit_report, values]);
            await this.env.services.action.doAction({ type: "ir.actions.act_window_close" });
            await this.model.root.load(); // reload
            return false;
        }
        return super.beforeExecuteActionButton(...arguments);
    }
}

export const auditReportFormController = {
    ...formView,
    Controller: AuditReportFormController,
};

registry.category("views").add("audit_report_form_controller", auditReportFormController);
