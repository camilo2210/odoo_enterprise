import { registry } from "@web/core/registry";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { serializeDate } from "@web/core/l10n/dates";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";

export class PayslipBatchFormController extends FormController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    selectEmployees() {
        return executeButtonCallback(this.ui.activeElement, async () => {
            const isValid = await this.model.root.checkValidity({ displayNotification: true });
            if (!isValid) {
                return;
            }
            const employeeListAction = await this.orm.call("hr.payslip.run", "action_payroll_hr_version_list_view_payrun", [
                [],
                serializeDate(this.model.root.data.date_start),
                serializeDate(this.model.root.data.date_end),
                this.model.root.data.structure_id?.id,
                this.model.root.data.company_id?.id,
                this.model.root.data.employee_type_ids?._currentIds || [],
            ]);
            /**
             * after adding employee_type_ids, this.model.root.data started containing
             * a relational field object that keeps a reference to the client model.
             * That introduces a circular reference (record → relation → model → context → record)
             * Action contexts are deep-copied via JSON, and JSON can’t handle circular structures. So
             * instead of passing this.model.root.data, we pass a plain serializable snapshot (no
             * proxies/relations), which avoids the cycle
             */
            const rawRecord = {
                date_start: this.model.root.data.date_start,
                date_end: this.model.root.data.date_end,
                structure_id: this.model.root.data.structure_id
                    ? {
                        id: this.model.root.data.structure_id.id,
                        display_name: this.model.root.data.structure_id.display_name,
                    }
                    : false,
                company_id: this.model.root.data.company_id?.id || false,
                employee_type_ids: this.model.root.data.employee_type_ids?._currentIds || [],
            };

            return this.actionService.doAction({
                ...employeeListAction,
                help: markup(employeeListAction.help),
                context: {
                    hide_off_cycle_btn: true,
                    raw_record: rawRecord,
                    payrun_date_start: serializeDate(this.model.root.data.date_start),
                    payrun_date_end: serializeDate(this.model.root.data.date_end),
                },
            });
        });
    }
}

registry.category("views").add("hr_payslip_batch_form", {
    ...formView,
    Controller: PayslipBatchFormController,
    buttonDialogTemplate: "hr_payroll.PayslipBatchFormView.Buttons"
});
