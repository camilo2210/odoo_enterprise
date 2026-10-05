import { HrHolidaysGanttRenderer } from "@hr_holidays_gantt/views/gantt/hr_holidays_gantt_renderer";
import { PayrollHolidaysGanttRendererControls } from "./payroll_holidays_gantt_renderer_controls";
import { RepeatedActionTipTracker } from "@hr_payroll/js/repeated_action_tip_tracker";
import { _t } from "@web/core/l10n/translation";

export class PayrollHolidaysGanttRenderer extends HrHolidaysGanttRenderer {
    static components = {
        ...HrHolidaysGanttRenderer.components,
        GanttRendererControls: PayrollHolidaysGanttRendererControls,
    };

    setup() {
        super.setup();
        this.multiSelectTipTracker = new RepeatedActionTipTracker();
    }

    onCellClicked(rowId, column, row) {
        if (this.ctrlPressed) {
            this.multiSelectTipTracker.reset();
        } else {
            const shouldShowTip = this.multiSelectTipTracker.registerAction(
                "cell_click_no_ctrl"
            );
            if (shouldShowTip) {
                this.notificationService.add(_t("Tip: Ctrl-Click to multi-select"), {
                    type: "info",
                });
            }
        }
        return super.onCellClicked(rowId, column, row);
    }

}