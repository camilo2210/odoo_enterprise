import { _t } from "@web/core/l10n/translation";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nPHReportStockFilters extends AccountReportFilters {
    get filterExtraOptionsData() {
        return {
            ...super.filterExtraOptionsData,
            'filter_no_stock': {
                'name': _t("Hide Out of Stock"),
            },
        };
    }

    get selectedExtraOptions() {
        let selectedExtraOptionsName = super.selectedExtraOptions;

        if (this.controller.cachedFilterOptions().filter_no_stock) {
            const hideZeroQtyLine = _t("Hide Out of Stock");

            selectedExtraOptionsName = selectedExtraOptionsName
                ? `${selectedExtraOptionsName}, ${hideZeroQtyLine}`
                : hideZeroQtyLine;
        }

        return selectedExtraOptionsName;
    }
};

AccountReportController.registerCustomComponent(L10nPHReportStockFilters);
