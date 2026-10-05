import { patch } from "@web/core/utils/patch";
import { AccountReportLineCellEditableDateTime } from "@account_reports/components/account_report/line_cell_editable/line_cell_editable_datetime";
import { formatDateTime } from "@web/core/l10n/dates";

patch(AccountReportLineCellEditableDateTime.prototype, {
    get pickerProps() {
        const props = super.pickerProps;
        if (this.figureType === "datetime_year") {
            props.minPrecision = "years";
            props.type = "date";
        }
        return props;
    },

    get inputValue() {
        if (this.figureType === "datetime_year") {
            return formatDateTime(this.datetime(), { tz: this.tz, format: "yyyy" });
        }
        return super.inputValue;
    },
});
