import { PayrollAvatarCard } from "@hr_payroll/core/web/avatar_card/payroll_avatar_card";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(PayrollAvatarCard.prototype, {
    get payrollInfo() {
        const info = super.payrollInfo;
        if (!info) {
            return info;
        }
        const emp = this.employee;
        if (emp.company_id?.country_code !== "BE") {
            return info;
        }
        const category = emp.l10n_be_salary_scale_id?.name || null;
        const hasBelgianScale = ["200", "302"].includes(emp.l10n_be_egov3_code);
        let years, months;
        if (hasBelgianScale) {
            years = emp.l10n_be_computed_seniority_years || 0;
            months = emp.l10n_be_computed_seniority_months || 0;
        } else {
            years = (emp.l10n_be_scale_seniority || 0) + (emp.l10n_be_company_seniority_years || 0) + Math.floor(((emp.l10n_be_scale_seniority_months || 0) + (emp.l10n_be_company_seniority_months || 0)) / 12);
            months = ((emp.l10n_be_scale_seniority_months || 0) + (emp.l10n_be_company_seniority_months || 0)) % 12;
        }
        const parts = [];
        if (years) {
            parts.push(years === 1 ? _t("1 year") : _t("%s years", years));
        }
        if (months) {
            parts.push(months === 1 ? _t("1 month") : _t("%s months", months));
        }
        const seniority = parts.join(" ") || info.seniority;
        return { ...info, category, seniority };
    },
});
