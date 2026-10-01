import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { exportTimeOffRecords } from "@hr_holidays/views/hr_leave_export";
import { useBus } from "@web/core/utils/hooks";

export class HrHolidaysGanttController extends hrGanttView.Controller {
    setup() {
        super.setup();
        useBus(this.env.searchModel, "direct-export-data", () => this.onDirectExportData());
    }

    async onDirectExportData() {
        const { resModel } = this.model.metaData;
        const { domain, context } = this.model.searchParams;
        await exportTimeOffRecords({ resModel, domain, context });
    }
}
