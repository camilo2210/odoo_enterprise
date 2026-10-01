import { VersionPayrunListController } from "@hr_payroll/views/payslip_run_version_list/hr_version_list_controller"
import { patch } from "@web/core/utils/patch";

patch(VersionPayrunListController.prototype, {
    buildRawRecord(rawRecord) {
        // In Hong Kong, set the l10n_hk_payroll_group_id & l10n_hk_payroll_scheme_id field when creating the record.
        if (rawRecord.country_code === "HK")
        {
            return {
                ...rawRecord,
                date_start: luxon.DateTime.fromISO(rawRecord.date_start).toISODate(),
                date_end: luxon.DateTime.fromISO(rawRecord.date_end).toISODate(),
                structure_id: rawRecord.structure_id.id,
                company_id: rawRecord.company_id,
                employee_type_ids: rawRecord.employee_type_ids || [],
                l10n_hk_payroll_group_id: rawRecord.l10n_hk_payroll_group_id?.id,
                l10n_hk_payroll_scheme_id: rawRecord.l10n_hk_payroll_scheme_id?.id,
            };
        }
        return super.buildRawRecord(rawRecord);
    }
});
