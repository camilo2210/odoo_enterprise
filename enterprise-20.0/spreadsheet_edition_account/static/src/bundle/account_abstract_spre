import { patch } from "@web/core/utils/patch";
import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";
const { DateTime } = luxon;

patch(AbstractSpreadsheetAction.prototype, {
    getModelConfig() {
        const config = super.getModelConfig();
        config.custom = {
            ...config.custom,
            currentFiscalYearStart: DateTime.fromISO(this.data.current_fiscal_year_start),
            currentFiscalYearEnd: DateTime.fromISO(this.data.current_fiscal_year_end),
        };
        return config;
    },
});
