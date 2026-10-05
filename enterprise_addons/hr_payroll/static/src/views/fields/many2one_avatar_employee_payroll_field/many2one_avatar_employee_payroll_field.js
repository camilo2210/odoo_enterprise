import { Many2OneAvatarEmployeeField } from "@hr/views/fields/many2one_avatar_employee_field/many2one_avatar_employee_field";
import { PayrollAvatar } from "@hr_payroll/core/web/avatar_card/payroll_avatar_card";
import { registry } from "@web/core/registry";
import { buildM2OFieldDescription, extractM2OFieldProps } from "@web/views/fields/many2one/many2one_field";

export class Many2OneAvatarEmployeePayrollField extends Many2OneAvatarEmployeeField {
    static template = "hr_payroll.Many2OneAvatarEmployeePayrollField";
    static components = { ...Many2OneAvatarEmployeeField.components, PayrollAvatar };

    get wageOverride() {
        const { wage, hourly_wage: hourlyWage, wage_type: wageType } = this.props.record.data;
        if (wage === null && hourlyWage === null) {
            return undefined;
        }
        return { wage, hourlyWage, wageType};
    }

    get payrollAvatarProps() {
        return {
            wageOverride: this.wageOverride,
            versionId: this.props.record.data.version_id.id,
            payslipId: this.props.record.resId,
            payslipDate: luxon.DateTime.fromISO(this.props.record.data.date_from).toISODate(),
        };
    }
}

registry.category("fields").add("many2one_avatar_employee_payroll", {
    ...buildM2OFieldDescription(Many2OneAvatarEmployeePayrollField),
    relatedFields: [{ name: "write_date", type: "datetime" }],
    additionalClasses: [
        "o_field_many2one_avatar",
        "o_field_many2one_avatar_user",
    ],
    fieldDependencies: [
        { name: "wage", type: "monetary" },
        { name: "hourly_wage", type: "monetary" },
        { name: "wage_type", type: "selection" },
        { name: "version_id", type: "many2one" },
        { name: "date_from", type: "date" },
    ],
    extractProps(staticInfo, dynamicInfo) {
        return {
            ...extractM2OFieldProps(staticInfo, dynamicInfo),
            relation: staticInfo.options.relation,
            canOpen:
                "no_open" in staticInfo.options
                    ? !staticInfo.options.no_open
                    : staticInfo.viewType === "form",
        };
    },
});
