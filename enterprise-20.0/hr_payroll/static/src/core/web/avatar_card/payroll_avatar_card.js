import { useProps, t } from "@odoo/owl";
import { AvatarCard } from "@mail/core/web/avatar_card/avatar_card";
import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { usePopover } from "@web/core/popover/popover_hook";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";

const wageOverrideType = t.object({
    hourlyWage: t.number().optional(),
    wage: t.number().optional(),
    wageType: t.string().optional(),
});

export class PayrollAvatarCard extends AvatarCard {
    setup() {
        super.setup(...arguments);
        this.payrollProps = useProps({ wageOverride: wageOverrideType.optional() });
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
        return {
            wage: `${formatMonetary(wageAmount, { currencyId: emp.currency_id?.id })} ${suffix}`,
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
        this.payrollProps = useProps({ wageOverride: wageOverrideType.optional() });
        this.avatarCard = usePopover(PayrollAvatarCard);
    }

    get popoverProps() {
        return {
            ...super.popoverProps,
            ...(this.payrollProps.wageOverride
                ? { wageOverride: this.payrollProps.wageOverride }
                : {}),
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
