import { hrGanttView } from "@hr_gantt/hr_gantt_view";
import { HrHolidaysGanttMultiSelectionButtons } from "./hr_holidays_gantt_multi_selection_buttons";
import { HrHolidaysSplitTool } from "./hr_holidays_split_tool";
import { formatFloatTime } from "@web/views/fields/formatters";
import { HrHolidayPopover } from "@hr_holidays_gantt/components/hr_holidays_popover/hr_holidays_gantt_popover";
import { HrHolidaysGanttEmployeeAvatar } from "@hr_holidays_gantt/core/web/avatar_card/hr_holidays_gantt_avatar_card";
import { getColumnStart } from "@web_gantt/gantt_helpers";
import { localization } from "@web/core/l10n/localization";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { onWillStart, signal } from "@odoo/owl";

// Limit how many buttons are displayed in the menu to avoid overflow
const MAX_QUICK_ADD_BUTTONS = 4;

export class HrHolidaysGanttRenderer extends hrGanttView.Renderer {
    static template = "hr_holidays_gantt.HrHolidaysGanttRenderer";
    static pillTemplate = "hr_holidays_gantt.HrHolidaysGanttRenderer.Pill";
    static progressBarLabelTemplate = "hr_holidays_gantt.HrHolidaysGanttRenderer.ProgressBarLabel";
    static rowContentTemplate = "hr_holidays_gantt.HrHolidaysGanttRenderer.RowContent";
    static components = {
        ...hrGanttView.Renderer.components,
        Avatar: HrHolidaysGanttEmployeeAvatar,
        Popover: HrHolidayPopover,
        MultiSelectionButtons: HrHolidaysGanttMultiSelectionButtons,
        HrHolidaysSplitTool,
    };

    setup() {
        super.setup();
        this.hrHolidayPopoverService = useService("hrHolidayPopoverService");
        this.hrHolidayPopoverService.setup(this.model.metaData, this.additionalFieldsToFetch);
        this.notificationService = useService("notification");
        this.splitTarget = null;
        this.splitToolPosition = signal(null);
        this.canSeeWorkEntryCode = false;
        this.canSplitLeave = false;
        onWillStart(async () => {
            this.canSeeWorkEntryCode = await user.hasGroup("hr_holidays.group_hr_holidays_user");
            this.canSplitLeave = this.canSeeWorkEntryCode;
        });
    }

    /**
     * @override
     */
    getDurationStr(duration) {
        return formatFloatTime(duration, {
            noLeadingZeroHour: true,
        }).replace(/(:00|:)/g, "h");
    }

    /**
     * @override
     */
    getDisplayName(pill) {
        const { computePillDisplayName, scale } = this.model.metaData;
        const { id: scaleId } = scale;
        const { record } = pill;
        if (!computePillDisplayName) {
            return record.display_name;
        }
        if (this.canSeeWorkEntryCode && record.display_code) {
            return record.display_code;
        }
        if (scaleId === "month") {
            return record.display_code || record.work_entry_type_id?.display_name || "";
        }
        if (scaleId === "week") {
            return record.work_entry_type_id?.display_name || "";
        }
        return record.display_name || "";
    }

    get additionalFieldsToFetch() {
        const { dateStartField, dateStopField, fields } = this.model.metaData;
        return [
            { name: "employee_id", type: "many2one", relation: "hr.employee", readonly: false },
            { name: "work_entry_type_id", type: "many2one", relation: "hr.work.entry.type", readonly: false },
            { name: dateStartField, type: "datetime", readonly: false },
            { name: dateStopField, type: "datetime", readonly: false },
            { name: "state", type: "selection", readonly: false },
            { name: "is_manager", type: "boolean", readonly: true },
            { name: "can_approve", type: "boolean", readonly: true },
            { name: "can_validate", type: "boolean", readonly: true },
            { name: "can_refuse", type: "boolean", readonly: true },
            { name: "can_back_to_approve", type: "boolean", readonly: true },
            { name: "display_code", type: "char", readonly: true },
            { name: "duration_display", type: "char", readonly: true },
        ].filter((f) => f.name in fields);
    }

    /**
     * @override
     */
    progressBarIsVisible() {
        return false;
    }

    /**
     * @override
     */
    getPopoverProps(pill) {
        const { record } = pill;
        const { canEdit } = this.model.metaData;
        return {
            readonly: !canEdit || record.state != "confirm",
            onReload: async () => await this.model.fetchData(),
            originalRecord: record,
            getDurationStr: this.getDurationStr,
            useWorkEntryCode: this.canSeeWorkEntryCode,
            recordProps: this.hrHolidayPopoverService.recordProps,
            archInfo: this.hrHolidayPopoverService.archInfo,
        };
    }

    /**
     * @override
     */
    getAvatarProps(row) {
        return {
            ...super.getAvatarProps(row),
            scale: this.model.metaData.rangeId,
        };
    }

    get canSplit() {
        return (
            !this.uiService.isSmall &&
            this.canSplitLeave &&
            this.model.metaData.canEdit &&
            this.model.metaData.resModel === "hr.leave" &&
            !this.model.useSampleModel
        );
    }

    /**
     * @override
     */
    computeDerivedParamsFromHover() {
        super.computeDerivedParamsFromHover(...arguments);
        this.splitTarget = this.getSplitTarget();
        this.splitToolPosition.set(
            this.splitTarget &&
                this.getGridPosition({
                    row: this.splitTarget.pill.grid.row,
                    column: [this.splitTarget.col, this.splitTarget.col + 1],
                })
        );
    }

    getSplitTarget() {
        if (!this.canSplit || this.isDragging || this.connectorDragState.dragging) {
            return null;
        }
        const pillEl = this.hovered.pill;
        const cellEl = this.cellForDrag.el;
        if (!pillEl || !cellEl) {
            return null;
        }
        const pill = this.pills[pillEl.dataset.pillId];
        if (!pill) {
            return null;
        }

        // Snap to the cell edge (day boundary) the cursor is within 8px of.
        const { cellPart } = this.model.metaData.scale;
        const rtl = localization.direction === "rtl";
        const { x, width } = cellEl.getBoundingClientRect();
        const cursorX = this.cursorPosition.x;
        const startBorder = rtl ? x + width : x;
        const endBorder = rtl ? x : x + width;
        let col = getColumnStart(getComputedStyle(cellEl));
        if (Math.abs(cursorX - endBorder) <= 8) {
            col += cellPart;
        } else if (Math.abs(cursorX - startBorder) > 8) {
            return null;
        }

        // Only allow splitting on a day boundary strictly inside the pill.
        const [first, last] = pill.grid.column;
        if (col <= first || col >= last || (col - 1) % cellPart !== 0) {
            return null;
        }
        return { pill, col };
    }

    /**
     * @override
     */
    onPillClicked(ev, pill) {
        if (this.canSplit && this.splitTarget) {
            this.canSplitLeave = false;
            this.onPillSplitToolClicked(this.splitTarget.pill, this.splitTarget.col).then(() => {
                this.canSplitLeave = this.canSeeWorkEntryCode
            });
            this.splitTarget = null;
            this.splitToolPosition.set(null);
            this.popover.close();
            return;
        }
        return super.onPillClicked(...arguments);
    }

    async onPillSplitToolClicked(pill, splitCol) {
        const { start: splitDate } = this.getColumnStartStop(splitCol, splitCol);
        const undoData = await this.model.splitLeave(pill.record, splitDate);
        if (!undoData?.new_leave_ids?.length) {
            return;
        }
        // Close the last split notification if any and show a new one with an Undo button.
        this.closeSplitNotificationFn?.();
        this.closeSplitNotificationFn = this.notificationService.add(
            _t("Time off divided into two"),
            {
                type: "success",
                buttons: [
                    {
                        name: _t("Undo"),
                        icon: "undo",
                        onClick: async () => {
                            const result = await this.model.undoSplitLeave(
                                pill.record.id,
                                undoData
                            );
                            this.closeSplitNotificationFn?.();
                            this.closeSplitNotificationFn = this.notificationService.add(
                                result
                                    ? _t("Time off merged back")
                                    : _t("Time off could not be merged back"),
                                { type: result ? "success" : "danger" }
                            );
                        },
                    },
                ],
            }
        );
    }

    getSelectedRecords(selectedCells, predicate) {
        const records = new Set();
        for (const selectedCell of selectedCells) {
            const recordsInSelectedCell = this.mappingCellToRecords[selectedCell];
            for (const record of recordsInSelectedCell || []) {
                if (predicate(record)) {
                    records.add(record);
                }
            }
        }
        return [...records];
    }

    getCellsInfoInContract(cellsInfo) {
        return cellsInfo;
    }

    getCellsInfoWithoutValidatedWorkEntry(selectedCells) {
        const cellsWithoutValidatedWorkEntry = [];
        for (const selectedCell of selectedCells) {
            const recordsInSelectedCell = this.mappingCellToRecords[selectedCell];
            if ((recordsInSelectedCell || []).some((r) => r.state === "validated")) {
                continue;
            }
            cellsWithoutValidatedWorkEntry.push(selectedCell);
        }
        return this.getCellsInfo(cellsWithoutValidatedWorkEntry);
    }

    /**
     * @override
     */
    prepareMultiSelectionButtonsReactive() {
        const result = super.prepareMultiSelectionButtonsReactive();
        result.onQuickAddDirect = (values) => this.onMultiAddDirect(values, this.selectedCells);
        result.onAdd = (multiCreateData) => this.onMultiCreate(multiCreateData, this.selectedCells);
        result.nbSelectedCells = 0;
        result.nbSelectedRows = 0;
        result.forceFullDuration = false;
        result.workTypes = [];
        result.pendingAdd = false;
        return result;
    }

    /**
     * @override
     */
    async updateMultiSelection() {
        super.updateMultiSelection(...arguments);

        const selectedCells = [...this.selectedCells];
        const cellsInfo = this.getCellsInfo(selectedCells);
        const uniqueRowIds = new Set(cellsInfo.map(info => info.rowId));

        const nbSelectedCells = selectedCells.length;
        const nbSelectedRows = uniqueRowIds.size;
        const isMultiEmployee = nbSelectedRows > 1;

        const reactiveState = {
            nbSelectedCells,
            nbSelectedRows,
            forceFullDuration: nbSelectedCells > 2,
            isMultiEmployee,
        };

        let start, stop, singleCellStop;
        if (cellsInfo.length) {
            start = cellsInfo[0].start;
            singleCellStop = cellsInfo[0].stop;
            stop = cellsInfo.reduce(
                (maxStop, cell) => (cell.stop > maxStop ? cell.stop : maxStop),
                cellsInfo[0].stop
            );
        }

        const firstCell = nbSelectedRows == 1 ? cellsInfo[0] : {};
        const employeeId = firstCell?.rowId ? this.model.getSchedule({ rowId: firstCell.rowId }).employee_id : undefined;
        const workTypes = await this.model.fetchEmployeesLeaveData(employeeId);

        Object.assign(this.multiSelectionButtonsReactive, {
            ...reactiveState,
            start: start,
            stop: stop,
            singleCellStop: singleCellStop,
            employeeId,
            workTypes: workTypes.slice(0, MAX_QUICK_ADD_BUTTONS),
        });
    }

    /**
     * @override
     */
    onMultiCreate(multiCreateData, selectedCells) {
        const cellsInfo = this.getCellsInfoInContract(this.getCellsInfo(selectedCells));
        return this.model.multiCreateRecords(multiCreateData, cellsInfo);
    }

    onMultiAddDirect(values, selectedCells) {
        const cellsInfo = this.getCellsInfoInContract(this.getCellsInfo(selectedCells));
        return this.model.multiReplaceRecords(values, cellsInfo, []);
    }

    /**
     * @override
     */
    getCellsInBlock(block) {
        const { cellPart } = this.model.metaData.scale;
        if (cellPart <= 1) {
            return super.getCellsInBlock(block);
        }
        const startCol = block.startCol - ((block.startCol - 1) % cellPart);
        const lastCol = block.endCol - 1;
        const endCol = lastCol - ((lastCol - 1) % cellPart) + cellPart;
        return super.getCellsInBlock({ ...block, startCol, endCol });
    }

    /**
     * @param {string} [groupedByField]
     * @param {false|number} [resId]
     * @returns {{ date: DateTime, hours: number }[]}
     */
    getRowAvailabilities(groupedByField, resId) {
        return this.getFromData(groupedByField, resId, "availabilities", []);
    }

    /**
     * @override
     */
    processRow(row, processAsGroup = true) {
        const processedRow = super.processRow(...arguments);
        const { groupedByField, parentResId, parentGroupedField, resId } = row;
        if (processedRow["rows"][0].unavailabilities) {
            processedRow["rows"][0].availabilities = this.getRowAvailabilities(
                parentGroupedField || groupedByField,
                parentResId ?? resId
            );
        }
        return processedRow;
    }

    ganttCellData(row, column) {
        const result = row.availabilities.find(
            (item) => item && item.date && new Date(item.date).toDateString() === new Date(column.start).toDateString()
        )?.hours;

        if (!result || result <= 0) {
            return "";
        }

        const hours = Math.floor(result);
        const minutes = Math.round((result - hours) * 60);

        // Only add the 'm' part if minutes > 0
        if (minutes > 0) {
            const paddedMinutes = minutes.toString().padStart(2, "0");
            return _t("%(hours)sh%(minutes)sm", {
                hours: hours,
                minutes: paddedMinutes
            });
        } else {
            return _t("%sh", hours);
        }
    }

    getDayPart(input) {
        const NOON = 12;
        const startHour = new Date(input.date).getUTCHours();

        const startTime = startHour;
        const stopTime = startHour + input.hours;

        // 1. Check if the entire block is before or at noon
        if (stopTime <= NOON) {
            return "morning";
        }

        // 2. Check if the entire block starts at or after noon
        if (startTime >= NOON) {
            return "afternoon";
        }

        // 3. If it spans across noon, decide based on "weight"
        // (Similar to your closestToNoon logic)
        const morningDuration = NOON - startTime;
        const afternoonDuration = stopTime - NOON;

        // If more than 1 hour exists in both, call it a full day
        // Otherwise, snap to the dominant half
        if (morningDuration >= 1 && afternoonDuration >= 1) {
            return "fullday";
        } else if (afternoonDuration > morningDuration) {
            return "afternoon";
        } else {
            return "morning";
        }
    }

    ganttAvailCellAttClass(row, column) {
        const result = row.availabilities.find(
            (item) => new Date(item.date).toDateString() === new Date(column.start).toDateString()
        );
        const dayPart = this.getDayPart(result);
        return {
            "start-0 top-0 w-50": dayPart === "morning", // left half of the cell
            "end-0 top-0 w-50": dayPart === "afternoon", // right half of the cell
            "w-100 align-items-center justify-content-center": dayPart === "fullday", // full cell if both today and disabled
        };
    }

    /**
     * @override
     */
    onCellDblClicked(column) {
        if (column.isFolded) {
            return;
        }
        this.multiSelectionButtonsReactive.pendingAdd = true;
    }

    /**
     * @override
     */
    onCellClicked(rowId, column, row) {
        if (!this.rowByIds[rowId]?.fromServer) {
            return;
        }
        super.onCellClicked(rowId, column, row);
    }

    /**
     * @override
     */
    isHoverable(row = null) {
        if (row && !row.fromServer) {
            return false;
        }
        return super.isHoverable(...arguments);
    }
}
