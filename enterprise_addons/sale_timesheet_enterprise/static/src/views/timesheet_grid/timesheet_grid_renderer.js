import { patch } from "@web/core/utils/patch";
import { TimesheetGridRenderer } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_renderer";

patch(TimesheetGridRenderer.prototype, {
    getFieldAdditionalProps(fieldName) {
        const props = super.getFieldAdditionalProps(fieldName);
        if (fieldName in this.props.model.targetLeftData) {
            props.targetLeft = this.props.model.targetLeftData[fieldName];
        }
        props.targetLimitsSet = this.props.model.targetLimitsSetData;
        return props;
    },
});
