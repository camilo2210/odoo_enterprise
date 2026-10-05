import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { FrequencyViewer } from "@timesheet_grid/components/aw_timesheet/frequency_viewer/frequency_viewer";

patch(FrequencyViewer.prototype, {
    get fields() {
        return {
            ...super.fields,
            billable: { type: "boolean", name: "billable", string: _t("Billable") },
        };
    },

    getRecordData(parsed, names) {
        return {
            ...super.getRecordData(parsed, names),
            billable: !!parsed.billable,
        };
    },
});
