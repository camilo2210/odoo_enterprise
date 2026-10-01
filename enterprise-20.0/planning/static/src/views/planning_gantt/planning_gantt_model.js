import { user } from "@web/core/user";
import { router } from "@web/core/browser/router";
import { Domain } from "@web/core/domain";
import { deserializeDateTime, serializeDateTime } from "@web/core/l10n/dates";
import { pick } from "@web/core/utils/objects";
import { localStartOf, localEndOf } from "@web_gantt/gantt_helpers";
import { GanttModel } from "@web_gantt/gantt_model";
import { usePlanningModelActions } from "../planning_hooks";

/**
 * @typedef {import("@web_gantt/gantt_model").Data} Data
 */

/**
 * @typedef {import("@web_gantt/gantt_model").MetaData} MetaData
 */


export class PlanningGanttModel extends GanttModel {
    /**
     * @override
     */
    setup() {
        super.setup(...arguments);
        this.getHighlightIds = usePlanningModelActions({
            getHighlightPlannedIds: () => this.env.searchModel.highlightPlannedIds,
            getContext: () => this.env.searchModel.context,
        }).getHighlightIds;
        this.isManager = null;
    }

    /**
     * @override
     */
    async load(searchParams) {
        if (this.isManager === null) {
            this.isManager = await user.hasGroup("planning.group_planning_manager");
        }

        const { context, domain } = searchParams;
        const displayRoleOpenShift = Boolean(context.show_role_open_shifts);
        let displayOpenShift = false;
        for (const node of domain) {
            if (
                node.length === 3 &&
                node[0] === "resource_ids" &&
                ["!=", "="].includes(node[1]) &&
                node[2] === false
            ) {
                return super.load({
                    ...searchParams,
                    context: { ...context, show_job_title: true },
                });
            }
            if (
                node.length === 3 &&
                ["department_id", "manager_id", "resource_ids"].includes(node[0])
            ) {
                displayOpenShift = true;
            }
        }
        if (displayRoleOpenShift) {
            searchParams.domain = Domain.and([domain, [["is_users_role", "=", true]]]).toList();
        } else if (displayOpenShift) {
            searchParams.domain = Domain.or([
                domain,
                Domain.and([
                    Domain.removeDomainLeaves(domain, [
                        "department_id",
                        "manager_id",
                        "resource_ids",
                    ]),
                    [["resource_ids", "=", false]],
                ]),
            ]).toList();
        }

        return super.load({ ...searchParams, context: { ...context, show_job_title: true } });
    }

    get hasMultiCreate() {
        return super.hasMultiCreate && this.isManager;
    }

    get showMultiCreateTimeRange() {
        return false;
    }

    /**
     * @override
     */
    _processGanttData(metaData, data, ganttData) {
        if ("working_periods" in ganttData) {
            const workingPeriods = {};
            for (const [resource_id, periods] of Object.entries(ganttData.working_periods)) {
                workingPeriods[resource_id] = periods.map(({ start, end }) => ({
                    start: deserializeDateTime(start),
                    end: end && deserializeDateTime(end),
                }));
            }
            data.workingPeriods = workingPeriods;
        }
        if ("planning_data" in ganttData) {
            if (!this.orm.isSample) {
                const workIntervals = {};
                for (const [resource_id, periods] of Object.entries(ganttData.planning_data.work_intervals)) {
                    workIntervals[resource_id] = periods.map((work_interval) =>
                        work_interval.map(deserializeDateTime)
                    )
                }
                data.workIntervals = workIntervals;
            }

            const isFlexibleHours = {};
            for (const [resource_id, value] of Object.entries(ganttData.planning_data.is_flexible)) {
                isFlexibleHours[resource_id] = value
            }
            data.isFlexibleHours = isFlexibleHours;

            const avgWorkHours = {};
            for (const [resource_id, value] of Object.entries(ganttData.planning_data.avg_hours)) {
                avgWorkHours[resource_id] = value
            }
            data.avgWorkHours = avgWorkHours;
        }
        super._processGanttData(metaData, data, ganttData);
    }

    /**
     * @override
     */
    _getUnscheduleData(eventId) {
        const data = {
            ...super._getUnscheduleData(...arguments),
            resource_ids: false,
            state: "1_draft",
        };
        const record = this.data.records.find((r) => r.id === eventId);
        if (record) {
            data.allocated_hours = record.allocated_hours;
        }
        return data;
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @returns {Object}
     */
    getAdditionalContext() {
        const { records } = this.data;
        const { startDate, scale, rangeId } = this.metaData;
        const defaultEmployeeIds = new Set();
        for (const record of records) {
            if (record.employee_public_ids) {
                for (const employeeId of record.employee_public_ids) {
                    defaultEmployeeIds.add(employeeId);
                }
            }
        }
        let stopDate = this.metaData.stopDate;
        if (this.metaData.ranges && rangeId in this.metaData.ranges) {
            stopDate = localEndOf(startDate, rangeId);
        }
        return {
            ...this.searchParams.context,
            default_start_datetime: serializeDateTime(startDate),
            default_end_datetime: serializeDateTime(stopDate),
            default_slot_ids: records.map((record) => record.id),
            scale: scale.id,
            active_domain: this.getDomain(),
            active_ids: records,
            default_employee_ids: [...defaultEmployeeIds],
        };
    }

    /**
     * @override
     */
    getDialogContext() {
        const context = super.getDialogContext(...arguments);
        delete context.show_job_title;
        delete context.highlight_planned;
        delete context.highlight_needs_attention;
        if (this.metaData.scale.id == 'day') {
            context.planning_keep_default_datetime = true;
        }
        return context;
    }

    /**
     * @returns {any[]}
     */
    getDomain() {
        const metaData = this._buildMetaData();
        return this._getDomain(metaData);
    }

    getRangeFromDate(rangeId, date) {
        const startDate = localStartOf(date, rangeId);
        const stopDate = startDate.plus({ [rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }

    /**
     * @override
     */
    getSchedule(params = {}) {
        const result = super.getSchedule(params);
        if (params.recurrence_update) {
            result.recurrence_update = params.recurrence_update;
        }
        return result;
    }

    /**
     * @override
     */
    async multiCreateRecords(multiCreateData, cellsInfo) {
        const values = await multiCreateData.record.getChanges();
        const records = [];
        if (values.template_id) {
            const [{ start_time, end_time, duration_days }] = await this.orm.read("planning.slot.template", [values.template_id], ["start_time", "end_time", "duration_days"]);
            const days_to_hours = duration_days > 1 ?  (duration_days - 1) * 24 : 0;
            for (const { rowId, start } of cellsInfo) {
                const schedule = this.getSchedule({
                    start: start.plus({ hour: start_time }),
                    stop: start.plus({ hour: end_time + days_to_hours }),
                    rowId,
                });
                records.push({ ...schedule, ...values });
            }
        }
        if (records.length) {
            await this.orm.create(this.metaData.resModel, records, {
                context: { ...this.searchParams.context, multi_create: true, add_materials_assigned_to_employees: true },
            });
            await this.fetchData();
        }
    }

    /**
     * @override
     */
    removeRedundantData(data, ids) {
        const result = super.removeRedundantData(data, ids);
        if (data.recurrence_update) {
            result.recurrence_update = data.recurrence_update;
        }
        return result;
    }

    async splitPill(start, stop, record) {
        const values = {
            start_datetime: serializeDateTime(start),
            end_datetime: serializeDateTime(stop)
        };
        const context = { planning_split_tool: true };
        const result = await this.orm.call(
            this.metaData.resModel,
            'split_pill',
            [[record.id]],
            { context, values: values },
        );
        await this.fetchData();
        return result;
    }

    //--------------------------------------------------------------------------
    // Protected
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    async _fetchData(metaData, additionalContext) {
        const context = {
            ...additionalContext,
            hide_planned_dates: true,
        }
        const [ highlightIds, ] = await Promise.all([
            this.getHighlightIds(),
            super._fetchData(metaData, context),
        ])
        const firstRow = this.data?.rows?.[0];
        if (firstRow.isGroup && this.orm.isSample && !this.isClosed(firstRow.id)) {
            this.closedRows.add(firstRow.id);
        }
        this.highlightIds = highlightIds;
    }

    /**
     * @override
     */
    _getGroupedBy(metaData, searchParams) {
        let groupBy = [...searchParams.groupBy];
        if (!this.firstLoad && searchParams.context.planning_groupby_role && !groupBy.length) {
            groupBy = ["role_id", "resource_ids"];
        }
        return super._getGroupedBy(metaData, { ...searchParams, groupBy });
    }

    /**
     * @override
     */
    _getInitialRangeParams() {
        // take parameters from url if set https://example.com/web?date_start=2020-11-08
        // this is used by the mail of planning.planning
        const urlState = router.current;
        if (urlState.date_start) {
            const focusDate = deserializeDateTime(urlState.date_start);
            let startDate;
            let stopDate;
            let rangeId;
            if (urlState.date_end) {
                const end = deserializeDateTime(urlState.date_end);
                if (localStartOf(focusDate, "week").equals(localStartOf(end, "week"))) {
                    ({ startDate, stopDate, rangeId } = this.getRangeFromDate("week", focusDate));
                } else if (localStartOf(focusDate, "month").equals(localStartOf(end, "month"))) {
                    ({ startDate, stopDate, rangeId } = this.getRangeFromDate("month", focusDate));
                } else {
                    startDate = focusDate;
                    stopDate = end;
                    rangeId = "custom";
                }
            } else {
                ({ startDate, stopDate, rangeId } = this.getRangeFromDate("month", focusDate));
            }
            return { focusDate, startDate, stopDate, rangeId };
        }
        return super._getInitialRangeParams(...arguments);
    }

    /**
     * @override
     */
    _getEventsToScheduleDomain(metaData) {
        const { dateStartField, dateStopField } = metaData;
        let baseDomain = this.searchParams.domain;

        const usersDomain = new Domain(baseDomain)
            .toList()
            .some(
                (leaf) => Array.isArray(leaf) && leaf.length === 3 && ["user_ids"].includes(leaf[0])
            );
        baseDomain = usersDomain
            ? Domain.or([baseDomain, [["resource_ids", "=", false]]])
            : baseDomain;

        const domain = Domain.and([
            Domain.removeDomainLeaves(baseDomain, [dateStartField, dateStopField]).toList(),
            ["&", [dateStartField, "=", false], [dateStopField, "=", false]],
        ]);
        return domain.toList();
    }

    /**
     * @override
     */
    _scheduleToData(schedule) {
        const allowedFields = [
            'recurrence_update',
            this.metaData.dateStartField,
            this.metaData.dateStopField,
            ...this.metaData.groupedBy,
        ];
        return pick(schedule, ...allowedFields);
    }

    /**
     * @override
     */
    _getRescheduleContext() {
        return {
            ...super._getRescheduleContext(),
            add_materials_assigned_to_employees: true,
        };
    }

    /**
     * @override
     */
    _getUnscheduleContext() {
        return {
            ...super._getUnscheduleContext(),
            from_slot_unscheduling: true,
        };
    }

    async _assignSlot(ids, schedule) {
        const [resolvedIds, data, context] = this._getRescheduleData(ids, schedule);
        return this.mutex.exec(async () => {
            let result;
            try {
                result = await this.orm.call(
                    this.metaData.resModel,
                    "assign_slot",
                    [resolvedIds, data],
                    {
                        context: {
                            ...context,
                            default_end_datetime: serializeDateTime(this.metaData.globalStop),
                            scale: this.metaData.scale.id,
                        },
                    }
                );
            } finally {
                await this.fetchData();
            }
            return result;
        });
    }

    /**
     * @override
     */
    async _fetchEventsToSchedule(params) {
        const result = await super._fetchEventsToSchedule(params);
        const activeId = this.searchParams.context.active_id;

        if (!activeId) {
            return result;
        }

        const index = result.records.findIndex(({ id }) => id === activeId);
        if (index > 0) {
            result.records.unshift(...result.records.splice(index, 1));
        }

        return result;
    }
}
