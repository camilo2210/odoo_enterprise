import { TimesheetGridModel } from "../timesheet_grid/timesheet_grid_model";

export class TimesheetToValidateGridModel extends TimesheetGridModel {
    setup(params) {
        const activeRangeName = this._getActiveRangeName(params);
        const range = params.ranges[activeRangeName];
        params.defaultAnchor = this.today.minus({
            [range.span]: 1,
        });
        super.setup(params);
    }
}
