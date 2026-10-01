import { ProjectGanttRenderer } from "@project_enterprise/views/project_gantt/project_gantt_renderer";
import { patch } from "@web/core/utils/patch";
import { userHasContractPeriods } from "../hooks";

patch(ProjectGanttRenderer.prototype, {
    /**
     * @override
     */
    ganttCellAttClass(row, column) {
        return {
            ...super.ganttCellAttClass(...arguments),
            o_user_has_no_working_periods: !this._userHasContractPeriods(row, column),
        };
    },
    /**
     * @param {number} column - Column index
     * @param {Row} row - Row Object
     */
    _userHasContractPeriods(row, column) {
        return userHasContractPeriods.call(this, row, column, "user_id");
    },
});
