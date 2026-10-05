import { Component, useProps, types as t } from "@odoo/owl";
import { formatDurationTimesheet } from "@timesheet_grid/utils/timer";
import { getAwRuleIcon } from "@timesheet_grid/utils/timesheets_assistant";
import { useService } from "@web/core/utils/hooks";

/**
 * Chronological ("timeline") rendering of the Timesheet Assistant suggestions. Purely
 * presentational: reads its data from the TimesheetAssistantModel passed as a prop, and reports
 * user interaction (selection, take, delete) back to the parent through callback props.
 */
export class TimesheetsAssistantTimeline extends Component {
    static template = "timesheet_grid.TimesheetsAssistantTimeline";
    props = useProps({
        model: t.object(),
        records: t.array(),
        showAwayTime: t.boolean(),
        selectedRowsSize: t.number(),
        isSelected: t.function(),
        getSelectionClass: t.function(),
        onMouseDown: t.function(),
        onMouseEnter: t.function(),
        onTake: t.function(),
        onDelete: t.function(),
    });
    formatDuration = formatDurationTimesheet;
    getIcon = getAwRuleIcon;

    uiService = useService("ui");
}
