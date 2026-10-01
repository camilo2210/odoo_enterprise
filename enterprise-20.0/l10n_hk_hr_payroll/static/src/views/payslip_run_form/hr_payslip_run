import { markup } from "@odoo/owl";
import { serializeDate } from "@web/core/l10n/dates";
import { executeButtonCallback } from "@web/views/view_button/view_button_hook";
import { PayslipBatchFormController } from "@hr_payroll/views/payslip_run_form/hr_payslip_run_form"
import { patch } from "@web/core/utils/patch";

patch(PayslipBatchFormController.prototype, {
    selectEmployees() {
        // In Hong Kong, we need the payroll group and scheme to properly handle the filtering of the employee.
        if (this.model.root.data.country_code === "HK")
        {
            return executeButtonCallback(this.ui.activeElement, async () => {
                const isValid = await this.model.root.checkValidity({ displayNotification: true });
                if (!isValid) {
                    return;
                }
                const employeeListAction = await this.orm.call("hr.payslip.run", "action_l10n_hk_hr_version_list_view_payrun", [
                    [],
                    serializeDate(this.model.root.data.date_start),
                    serializeDate(this.model.root.data.date_end),
                    this.model.root.data.structure_id?.id,
                    this.model.root.data.company_id?.id,
                    this.model.root.data.employee_type_ids?._currentIds || [],
                    this.model.root.data.l10n_hk_payroll_group_id?.id,
                    this.model.root.data.l10n_hk_payroll_scheme_id?.id,
                ]);

                const rawRecord = {
                    country_code: this.model.root.data.country_code,
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
                    l10n_hk_payroll_group_id: this.model.root.data.l10n_hk_payroll_group_id
                        ? {
                            id: this.model.root.data.l10n_hk_payroll_group_id.id,
                            display_name: this.model.root.data.l10n_hk_payroll_group_id.display_name,
                        }
                        : false,
                    l10n_hk_payroll_scheme_id: this.model.root.data.l10n_hk_payroll_scheme_id
                        ? {
                            id: this.model.root.data.l10n_hk_payroll_scheme_id.id,
                            display_name: this.model.root.data.l10n_hk_payroll_scheme_id.display_name,
                        }
                        : false,
                };

                return this.actionService.doAction({
                    ...employeeListAction,
                    help: markup(employeeListAction.help),
                    context: {
                        raw_record: rawRecord,
                        payrun_date_start: serializeDate(this.model.root.data.date_start),
                        payrun_date_end: serializeDate(this.model.root.data.date_end),
                    },
                });
            });
        }
        return super.selectEmployees(...arguments);
    }
});
