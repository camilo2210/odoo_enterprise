import { serializeDateTime } from "@web/core/l10n/dates";
import { parseServerValues } from "@web_gantt/gantt_model";
import { Domain } from "@web/core/domain";
import {localStartOf} from "@web_gantt/gantt_helpers";
import { hrGanttView } from "@hr_gantt/hr_gantt_view";

export class AttendanceGanttModel extends hrGanttView.Model {
    //-------------------------------------------------------------------------
    // Protected
    //-------------------------------------------------------------------------
    static services = [...hrGanttView.Model.services, "ui"];

    setup(params, services) {
        super.setup(...arguments);
        this.ui = services.ui;
    }

    /**
     * @override
     */
    _getDomain(metaData) {
        const { dateStartField, dateStopField, globalStart, globalStop } = metaData;
        const dateNow = luxon.DateTime.now();
        if (dateNow >= globalStart) {
            const domain = Domain.and([
                this.searchParams.domain,
                [
                    "&",
                    [dateStartField, "<", serializeDateTime(globalStop)],
                    "|",
                    "&",
                    [dateStartField, "<", serializeDateTime(dateNow)],
                    [dateStopField, "=", false],
                    [dateStopField, ">", serializeDateTime(globalStart)],
                ],
            ]);
            return domain.toList();
        } else {
            return super._getDomain(...arguments);
        }
    }

    _parseServerData(metaData, records) {
        const { dateStartField, dateStopField, fields } = metaData;
        /** @type {Record<string, any>[]} */
        const parsedRecords = super._parseServerData(...arguments);
        for (const record of records) {
            const parsedRecord = parseServerValues(fields, record);
            const dateStart = parsedRecord[dateStartField];
            const dateStop = parsedRecord[dateStopField];
            if (dateStart && !dateStop) {
                parsedRecord[dateStopField] = luxon.DateTime.now();
                parsedRecords.push(parsedRecord);
            }
        }
        return parsedRecords;
    }

    /**
     * @override
     */
    _processGanttData(metaData, data, ganttData) {
        super._processGanttData(metaData, data, ganttData);
        data.employeesWithoutContractIds = ganttData.employees_without_contract_ids || [];
    }

    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }

    /**
     * @override
     */
    getDialogContext(){
        const context = super.getDialogContext(...arguments);
        context['scale'] = this.metaData.scale.id;
        return context;
    }

    /**
     * @override
     */
    _processProgressBar(progressBar, warning) {
        const processedProgressBar = super._processProgressBar(...arguments);
        const { ratio } = processedProgressBar;
        processedProgressBar.available_formatted = `${processedProgressBar.value_formatted} / ${processedProgressBar.max_value_formatted}`;
        let extraString = "";
        if (ratio > 100) {
            extraString = `+${this._formatTime(progressBar.value - progressBar.max_value)}`;
        } else if (ratio < 100 && ratio > 0) {
            extraString = `${this._formatTime(progressBar.max_value - progressBar.value)} left`;
        }
        if (this.ui.size < 5) {
            processedProgressBar.available_formatted = extraString
                ? extraString
                : processedProgressBar.value_formatted;
        } else if (extraString) {
            processedProgressBar.available_formatted += ` (${extraString})`;
        }
        return processedProgressBar;
    }
}
