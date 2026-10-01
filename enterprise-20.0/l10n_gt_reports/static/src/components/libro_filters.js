import { _t } from "@web/core/l10n/translation";

import { AccountReportController } from "@account_reports/components/account_report/controller";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class L10nGtLibroReportFilters extends AccountReportFilters {
    get l10nGtLibroBooks() {
        return { sale: _t("Sales"), purchase: _t("Purchases") };
    }

    get l10nGtLibroSelectedBook() {
        return (
            this.l10nGtLibroBooks[this.controller.cachedFilterOptions().l10n_gt_libro_book] ||
            _t("Sales")
        );
    }

    selectL10nGtLibroBook(book) {
        this.filterClicked({ optionKey: "l10n_gt_libro_book", optionValue: book, reload: true });
    }
}

AccountReportController.registerCustomComponent(L10nGtLibroReportFilters);
