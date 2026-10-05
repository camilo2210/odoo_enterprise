import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { GanttModel } from "@web_gantt/gantt_model";

export class AppraisalGanttModel extends hrGanttView.Model {
    /**
     * @override
     */
    _getGroupedBy(metaData, searchParams) {
        // call original _getGroupedBy() to avoid forcing employee grouping
        return GanttModel.prototype._getGroupedBy.call(this, metaData, searchParams);
    }
}
