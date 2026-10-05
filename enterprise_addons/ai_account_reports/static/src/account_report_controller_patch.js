import { AccountReport } from "@account_reports/components/account_report/account_report";
import { useDataGetter } from "@ai/utils/bus_data_getter";
import { patch } from "@web/core/utils/patch";

patch(AccountReport.prototype, {
    setup() {
        super.setup(...arguments);
        useDataGetter("view", () => {
            const options = this.controller.options();
            return {
                current_account_report: {
                    action_id: this.controller.action.id,
                    action_report_id: this.controller.actionReportId,
                    report_id: options.report_id,
                    options,
                },
            };
        });
    },
});
