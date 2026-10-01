import { _t } from "@web/core/l10n/translation";
import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class IntercoComparisonReportFilters extends AccountReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'hide_tax_lines': {
                'name': _t("Hide Tax Lines"),
            },
        };
    }
}

AccountReportController.registerCustomComponent(IntercoComparisonReportFilters);
