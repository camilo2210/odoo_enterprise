declare module "models" {
    export interface HrEmployee {
        l10n_be_company_seniority_months: number|undefined;
        l10n_be_company_seniority_years: number|undefined;
        l10n_be_computed_seniority_months: number|undefined;
        l10n_be_computed_seniority_years: number|undefined;
        l10n_be_egov3_code: string|undefined;
        l10n_be_scale_seniority: number|undefined;
        l10n_be_scale_seniority_months: number|undefined;
    }
    export interface ResCompany {
        country_code: string;
    }
}
