import { serializeDateTime } from "@web/core/l10n/dates";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { formatFloatTime } from "@web/views/fields/formatters";
import { getIntersection, getUnionOfIntersections } from "@web_gantt/gantt_helpers";
import { GanttRenderer } from "@web_gantt/gantt_renderer";

const { Duration } = luxon;

export class MRPWorkorderGanttRenderer extends GanttRenderer {
    setup() {
        super.setup();
        this.action = useService("action");
        if (browser.localStorage.getItem(this.keyExpandSidePanel) === null) {
            this.sidePanelState.sidePanelExpanded = false;
        }
        if (browser.localStorage.getItem(this.keyShowConnectors) === null) {
            this.showConnectorsState.value = false;
        }
    }

    addTo(pill, group) {
        const { unavailabilities } = this.model.data;
        const { start, stop } = this.getSubColumnFromColNumber(group.col);
        const { date_start: otherStart, date_finished: otherStop } = pill.record;
        const interval = getIntersection(
            [start, stop.plus({ seconds: 1 })],
            [otherStart, otherStop]
        );
        let pillDuration = interval[1].diff(interval[0]);
        const workcenterId = pill.record.workcenter_id && pill.record.workcenter_id.id;
        const workCenterUnavailabilities = (
            unavailabilities.workcenter_id?.[workcenterId] || []
        ).map(({ start, stop }) => [start, stop]);
        const union = getUnionOfIntersections(interval, workCenterUnavailabilities);
        for (const [otherStart, otherEnd] of union) {
            pillDuration -= otherEnd.diff(otherStart);
        }
        if (!pillDuration) {
            return false;
        }
        group.pills.push(pill);
        group.aggregateValue += pillDuration;
        return true;
    }

    getGroupPillDisplayName(pill) {
        const hours = Duration.fromMillis(pill.aggregateValue).as("hour");
        return formatFloatTime(hours);
    }

    shouldComputeAggregateValues(row) {
        // compute aggregate values only for total row
        return row.id === "[]";
    }

    shouldMergeGroups() {
        return false;
    }

    onConnectorHover() {
        return !this.connectorDragState.dragging;
    }

    async list(workcenterId, date_to_plan_on = null) {
        this.action.doAction("mrp_workorder.mrp_workcenter_workorders_gantt", {
            additionalContext: {
                search_default_workcenter_id: workcenterId,
                workcenter_to_plan_on: workcenterId,
                date_to_plan_on: date_to_plan_on,
            },
            onClose: async () => {
                await this.model.fetchData();
            },
        });
    }

    focusFirstPill(rowId) {
        super.focusFirstPill(rowId);
        if (this.model.metaData.groupedBy.at(-1) == "workcenter_id") {
            const workcenter = this.rows.find((r) => r.id === rowId).resId;
            this.list(workcenter);
        }
    }

    onCellClicked(rowId, column, row) {
        super.onCellClicked(rowId, column, row);
        if (this.model.metaData.groupedBy.at(-1) == "workcenter_id") {
            const workcenter = this.rows.find((r) => r.id === rowId).resId;
            this.list(workcenter, serializeDateTime(column.start));
        }
    }
}
