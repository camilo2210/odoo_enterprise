import { GanttRendererControls } from "@web_gantt/gantt_renderer_controls";
const { DateTime } = luxon;

export class HrGanttRendererControls extends GanttRendererControls {
    /**
     * @override
     */
    selectRangeId(rangeId) {
        const today = DateTime.local().startOf("day");
        // When today is off screen, keep the framework behaviour (viewport centre).
        if (today < this.state.startDate || this.state.stopDate < today) {
            return super.selectRangeId(rangeId);
        }
        Object.assign(this.state, this.model.getRangeFromDate(rangeId, today));
        delete this.state.keepCurrentFocusDate;
        this.updateMetaData();
    }
}
