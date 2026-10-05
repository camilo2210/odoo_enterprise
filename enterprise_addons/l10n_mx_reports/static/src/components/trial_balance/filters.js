import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";


export class L10nMXTrialBalanceReportFilters extends AccountReportFilters {
    selectDateFilter(periodType) {
        this.controller.cachedFilterOptions().l10n_mx_month_13 = periodType === 'l10n_mx_month_13';
        super.selectDateFilter(periodType);
    }
}

AccountReportController.registerCustomComponent(L10nMXTrialBalanceReportFilters);
