import { useProps, t } from "@odoo/owl";
import { HrHolidaysGanttAvatarCard } from "@hr_holidays_gantt/core/web/avatar_card/hr_holidays_gantt_avatar_card";
import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { usePopover } from "@web/core/popover/popover_hook";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { user } from "@web/core/user";

const wageOverrideType = t.object({
    hourlyWage: t.number().optional(),
    wage: t.number().optional(),
    wageType: t.string().optional(),
});

const payrollPropsType = {
    wageOverride: wageOverrideType.optional(),
    versionId: t.number().optional(),
    payslipId: t.number().optional(),
    payslipDate: t.customValidator(t.string(), (v) => v?.match(/^\d{4}-\d{2}-\d{2}$/)).optional(),
};

export class PayrollAvatarCard extends HrHolidaysGanttAvatarCard {
    static template = "hr_payroll.PayrollAvatarCard";
    payrollProps = useProps(payrollPropsType);

    setup() {
        super.setup(...arguments);
        this.state.salaryAttachments = [];
    }

    /**
     * @override
     */
    async _loadPayrollCardData() {
        this.isPayrollUser = await user.hasGroup("hr_payroll.group_hr_payroll_user");
        this.canCreateSalaryAttachment = this.isPayrollUser && this.payrollProps.payslipId;
        if (!this.isPayrollUser) {
            return;
        }
        const payslipId = this.payrollProps.payslipId;
        const salaryAttachmentPromise = payslipId
            ? this.orm.searchRead(
                  "hr.salary.attachment",
                  [["payslip_ids", "in", [payslipId]]],
                  ["salary_rule_id", "amount", "currency_id"]
              )
            : Promise.resolve([]);

        const [, salaryAttachmentData] = await Promise.all([
            super._loadPayrollCardData(),
            salaryAttachmentPromise,
        ]);

        if (!salaryAttachmentData.length) {
            return;
        }
        this.state.salaryAttachments = salaryAttachmentData.map((attachment) => {
            const currencyId = attachment.currency_id && attachment.currency_id[0];
            return {
                id: attachment.id,
                salaryRule: attachment.salary_rule_id ? attachment.salary_rule_id[1] : "",
                amount: currencyId
                    ? formatMonetary(attachment.amount, { currencyId })
                    : attachment.amount,
            };
        });
    }

    openSalaryAttachment(attachmentId) {
        const name = attachmentId ? _t("Edit Salary Attachment") : _t("New Salary Attachment");
        this.action.doAction({
            name: name,
            type: "ir.actions.act_window",
            res_model: "hr.salary.attachment",
            res_id: attachmentId,
            views: [[false, "form"]],
            target: "new",
            context: {
                default_employee_id: this.employee?.id,
                default_date_start: this.payrollProps.payslipDate,
            },
        });
    }

    get hasFooter() {
        return false;
    }

    get payrollInfo() {
        const emp = this.employee;
        if (emp?.wage === undefined || emp?.wage === null) {
            return null;
        }
        const override = this.payrollProps.wageOverride;
        const isHourly = (override?.wageType || emp.wage_type) === "hourly";
        const suffix = isHourly ? _t("/ hour") : _t("/ month");
        let wageAmount;
        if (override) {
            wageAmount = isHourly ? (override.hourlyWage ?? override.wage) : override.wage;
        } else {
            wageAmount = isHourly ? emp.hourly_wage : emp.wage;
        }
        const currencyDecimals = emp.currency_id?.decimal_places || 2;
        return {
            wage: `${formatMonetary(wageAmount, {
                currencyId: emp.currency_id?.id,
                digits: [16, isHourly ? 4 : currencyDecimals],
            })} ${suffix}`,
            category: emp.employee_type_id?.name || null,
            seniority: this._getSeniority(emp.first_contract_date),
        };
    }

    _getSeniority(dateStr) {
        if (!dateStr) {
            return null;
        }
        const start = new Date(dateStr);
        const now = new Date();
        let years = now.getFullYear() - start.getFullYear();
        let months = now.getMonth() - start.getMonth();
        if (months < 0) {
            years--;
            months += 12;
        }
        const parts = [];
        if (years) {
            parts.push(years === 1 ? _t("1 year") : _t("%s years", years));
        }
        if (months) {
            parts.push(months === 1 ? _t("1 month") : _t("%s months", months));
        }
        return parts.join(" ") || _t("< 1 month");
    }
}

export class PayrollAvatar extends Avatar {
    static template = "hr_payroll.PayrollAvatar";

    setup() {
        super.setup(...arguments);
        this.payrollProps = useProps(payrollPropsType);
        this.avatarCard = usePopover(PayrollAvatarCard);
    }

    /**
     * @override
     */
    get popoverProps() {
        return {
            ...super.popoverProps,
            ...this.payrollProps,
        };
    }

    /**
     * @override
     */
    onClickAvatar(ev) {
        if (!this.uiService.isSmall) {
            ev.stopPropagation();
        }
        super.onClickAvatar(ev);
    }
}
