import { Record } from "@mail/model/export";
import { patch } from "@web/core/utils/patch";
import { fields } from "@mail/model/misc";
import { HrEmployee } from "@hr/core/common/hr_employee_model";
import { ResCompany } from "@mail/core/common/res_company_model";

class L10nBeSalaryScale extends Record {
    static _name = "l10n_be.salary.scale";
}
L10nBeSalaryScale.register();

patch(ResCompany.prototype, {
    setup() {
        super.setup();
        /** @type {string} */
        this.country_code = undefined;
    },
});

patch(HrEmployee.prototype, {
    setup() {
        super.setup();
        this.l10n_be_salary_scale_id = fields.One("l10n_be.salary.scale");
        /** @type {number|undefined} */
        this.l10n_be_company_seniority_months = undefined;
        /** @type {number|undefined} */
        this.l10n_be_company_seniority_years = undefined;
        /** @type {number|undefined} */
        this.l10n_be_computed_seniority_months = undefined;
        /** @type {number|undefined} */
        this.l10n_be_computed_seniority_years = undefined;
        /** @type {string|undefined} */
        this.l10n_be_egov3_code = undefined;
        /** @type {number|undefined} */
        this.l10n_be_scale_seniority = undefined;
        /** @type {number|undefined} */
        this.l10n_be_scale_seniority_months = undefined;
    },
});
