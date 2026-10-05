import { _t } from "@web/core/l10n/translation";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class SalesReportFilters extends AccountReportFilters {
    static template = "account_reports.SalesReportFilters";

    //------------------------------------------------------------------------------------------------------------------
    // Getters
    //------------------------------------------------------------------------------------------------------------------
    get selectedECSaleType() {
        const selected = this.controller.cachedFilterOptions().filter_sale_type_selection.filter(
            (saleType) => saleType.selected,
        );

        switch (selected.length) {
            case this.controller.cachedFilterOptions().filter_sale_type_selection.length:
                return _t("All");
            case 0:
                return _t("None");
            default:
                return selected.map((s) => s.name.substring(0, 1)).join(", ");
        }
    }
}

AccountReportController.registerCustomComponent(SalesReportFilters);
