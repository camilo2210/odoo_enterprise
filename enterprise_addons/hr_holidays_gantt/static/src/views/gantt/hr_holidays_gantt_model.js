import { serializeDate, deserializeDateTime } from "@web/core/l10n/dates";
import { localStartOf } from "@web_gantt/gantt_helpers";
import { hrGanttView } from "@hr_gantt/hr_gantt_view";


export class HrHolidaysGanttModel extends hrGanttView.Model {
    get showMultiCreateTimeRange() {
        return false;
    }

    getRange() {
        const { globalStart, globalStop } = this._buildMetaData();
        return { start: globalStart, end: globalStop.minus({ millisecond: 1 }) };
    }

    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }

    /** Merge the cells sharing a key into one range, keeping the widest span. */
    _mergeRanges(cellsInfo, keyFn) {
        const ranges = new Map();
        for (const cell of cellsInfo) {
            const key = keyFn(cell);
            const existing = ranges.get(key);
            if (!existing) {
                ranges.set(key, { start: cell.start, stop: cell.stop, rowId: cell.rowId });
                continue;
            }
            if (cell.start.toMillis() < existing.start.toMillis()) {
                existing.start = cell.start;
            }
            if (cell.stop.toMillis() > existing.stop.toMillis()) {
                existing.stop = cell.stop;
            }
        }
        return [...ranges.values()];
    }

    async multiReplaceRecords(values, cellsInfo, records) {
        if (!cellsInfo.length) {
            return;
        }
        const new_records = this._mergeRanges(cellsInfo, (cell) => cell.rowId).map((range) => ({
            ...this.getSchedule(range),
            ...values,
        }));
        // the replaced time off still overlaps the new one while it is created
        const created = await this.orm.create(this.metaData.resModel, new_records, {
            context: {
                ...this.searchParams.context,
                multi_create: true,
                leave_skip_date_check: true,
                multi_leave_request: true,  // see hr.leave._check_validity()
            },
        });
        if (records.length && created) {
            await this.orm.unlink(this.metaData.resModel, records.map((r) => r.id));
        }
        await this.fetchData();
    }

    _processProgressBar(progressBar, warning) {
        const processedProgressBar = super._processProgressBar(progressBar, warning);
        if (progressBar?.value != null) {
            processedProgressBar.value_formatted = `${Math.round(progressBar.value)}h`;
        }
        return processedProgressBar;
    }

    async fetchEmployeesLeaveData(employeeId) {
        const data = await this.orm.call(
            "hr.employee",
            "get_employee_available_leave_types",
            [employeeId]
        );
        return data;
    }

    async createRecord(records) {
        return this.orm.create(this.metaData.resModel, records, this.metaData.context);
    }

    /**
     * Split a time off (pill) into two at the given day, mirroring the planning
     * gantt "scissors" tool.
     */
    async splitLeave(record, splitDate) {
        const undoData = await this.orm.call(
            this.metaData.resModel,
            "gantt_split_leave",
            [[record.id], serializeDate(splitDate)],
            { context: this.searchParams.context }
        );
        await this.fetchData();
        return undoData;
    }

    /**
     * Undo a split previously performed by {@link splitLeave}.
     */
    async undoSplitLeave(recordId, undoData) {
        const result = await this.orm.call(
            this.metaData.resModel,
            "gantt_undo_split_leave",
            [
                [recordId],
                undoData.new_leave_ids,
                undoData.request_date_to,
                undoData.request_date_to_period,
                undoData.request_hour_to,
            ],
            { context: this.searchParams.context }
        );
        await this.fetchData();
        return result;
    }

    /**
     * Create a single time off per employee spanning the full selected range.
     * @override
     */
    async multiCreateRecords(multiCreateData, cellsInfo) {
        if (!cellsInfo.length) {
            return;
        }
        const values = await multiCreateData.record.getChanges();
        const recordData = multiCreateData.record.data;
        const timeRange = multiCreateData.timeRange;
        const { dateStartField, dateStopField } = this.metaData;
        const isHourly = recordData.work_entry_type_request_unit === "hour";
        const isPartialHalfDay = recordData.work_entry_type_request_unit === "half_day" && recordData.request_duration !== "full";
        const shouldSplitByDay = isHourly || isPartialHalfDay;
        const records = [];
        const cleanValues = { ...values };

        delete cleanValues.number_of_hours;
        delete cleanValues.number_of_days;
        if (isHourly) {
            cleanValues.request_duration = "specific";
            cleanValues.request_hour_from = recordData.request_hour_from;
            cleanValues.request_hour_to = recordData.request_hour_to;
        } else {
            delete cleanValues.request_hour_from;
            delete cleanValues.request_hour_to;
        }

        if (shouldSplitByDay) {
            delete cleanValues[dateStartField];
            delete cleanValues[dateStopField];
        }

        // on a lone day, a request the dialog made longer runs on into the days after
        const oneDaySelected = new Set(cellsInfo.map((cell) => cell.start.toISODate())).size === 1;
        const requestDateTo = isHourly && oneDaySelected && recordData.request_date_to;

        const buildRecord = ({ start, stop, rowId }) => {
            const rangeStart = timeRange ? start.set(timeRange.start.toObject()) : start;
            const rangeStop = timeRange ? stop.set(timeRange.end.toObject()) : stop;
            const schedule = this.getSchedule({ start: rangeStart, stop: rangeStop, rowId });
            if (!shouldSplitByDay) {
                // the selection carries the half days, the inverse maps them onto the request
                return { ...cleanValues, ...schedule };
            }
            // only the dates come from the selection, the rest from the dialog
            delete schedule[dateStartField];
            delete schedule[dateStopField];
            const lastDay = stop.minus({ second: 1 });
            return {
                ...cleanValues,
                ...schedule,
                request_date_from: serializeDate(rangeStart),
                request_date_to: serializeDate(
                    requestDateTo && requestDateTo > lastDay ? requestDateTo : lastDay
                ),
            };
        };

        if (shouldSplitByDay) {
            // Group by Day! (For Hourly, AM, and PM requests)
            // a day outside the schedule is left for the server to sort out, not skipped here
            const rangesByDay = this._mergeRanges(
                cellsInfo,
                (cell) => `${cell.rowId}_${cell.start.toISODate()}`
            );
            for (const range of rangesByDay) {
                records.push(buildRecord(range));
            }
        } else {
            // Group contiguous blocks by Employee Row and push EXACTLY ONE RECORD spanning the weekend gap
            const blocksByRow = this._mergeRanges(cellsInfo, (cell) => cell.rowId);
            for (const range of blocksByRow) {
                records.push(buildRecord(range));
            }
        }

        if (records.length > 0) {
            await this.orm.create(this.metaData.resModel, records, {
                context: {
                    ...this.searchParams.context,
                    multi_create: true,
                    multi_leave_request: true,  // see hr.leave._check_validity()
                },
            });
        }
        await this.fetchData();
    }

    /**
     * @override
     */
    _processGanttData(metaData, data, ganttData) {
        const processedAvailabilities = {};
        processedAvailabilities["employee_id"] = {};
        if ("availabilities" in ganttData) {
            for (const [resId, resAvailabilities] of Object.entries(
                ganttData.availabilities["employee_id"]
            )) {
                processedAvailabilities["employee_id"][resId] = resAvailabilities.map((u) => ({
                    date: deserializeDateTime(u.date),
                    hours: u.hours,
                }));
            }
        }
        data.availabilities = processedAvailabilities;
    }
}
