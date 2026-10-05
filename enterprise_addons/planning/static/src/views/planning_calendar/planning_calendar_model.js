import { Domain } from "@web/core/domain";
import { user } from "@web/core/user";
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { usePlanningModelActions } from "../planning_hooks";
import { planningAskRecurrenceUpdate } from "./planning_ask_recurrence_update/planning_ask_recurrence_update_hook";
import { _t } from "@web/core/l10n/translation";
import { serializeDateTime } from "@web/core/l10n/dates";
import { unique } from "@web/core/utils/arrays";

export class PlanningCalendarModel extends CalendarModel {
    static services = [...CalendarModel.services, "dialog", "orm"];

    setup(params, services) {
        // always fetch those fields as they'll be used by this model and the popover
        const extraFields = ["repeat", "allocated_hours", "allocated_percentage", "state"];
        params.fieldNames = unique(params.fieldNames.concat(extraFields));

        super.setup(...arguments);
        this.dialog = services.dialog;
        this.getHighlightIds = usePlanningModelActions({
            getHighlightPlannedIds: () => this.env.searchModel.highlightPlannedIds,
            getContext: () => this.env.searchModel._context,
        }).getHighlightIds;
        this.meta.scale = this.uiService.isSmall ? "day" : this.meta.scale;
        this.isManager = null;
    }

    async load(params = {}) {
        let groupProm;
        if (this.isManager === null) {
            groupProm = user.hasGroup("planning.group_planning_manager").then(result => this.isManager = result);
        }
        params.context = {
            ...(params.context ? params.context : this.meta.context),
            hide_planned_dates: true,
        }
        return Promise.all([super.load(...arguments), groupProm]);
    }

    get hasMultiCreate() {
        return super.hasMultiCreate && this.isManager;
    }

    get showMultiCreateTimeRange() {
        return false;
    }

    get defaultFilterLabel() {
        return _t("Open Shifts");
    }

    /**
     * @override
     */
    async loadRecords(data) {
        this.highlightIds = await this.getHighlightIds();
        return await super.loadRecords(data);
    }

    /**
     * @override
     */
    async updateRecord(record) {
        const rec = this.records[record.id];
        if (rec.rawRecord.repeat) {
            const recurrenceUpdate = await planningAskRecurrenceUpdate(this.dialog);
            if (!recurrenceUpdate) {
                return this.notify();
            }
            record.recurrenceUpdate = recurrenceUpdate;
        }
        return await super.updateRecord(...arguments);
    }

    /**
     * @override
     */
    buildRawRecord(partialRecord, options = {}) {
        if (options.batch_create_calendar) {
            let days_to_hours = 0;
            if (options.schedule[0]['duration_days'] > 1) {
                days_to_hours = (options.schedule[0]['duration_days'] - 1) * 24;
            }
            partialRecord.end = partialRecord.start.plus({ hour: options.schedule[0]['end_time'] + days_to_hours });
            partialRecord.start = partialRecord.start.plus({ hour: options.schedule[0]['start_time'] });
        }
        const result = super.buildRawRecord(partialRecord, options);
        if (partialRecord.recurrenceUpdate) {
            result.recurrence_update = partialRecord.recurrenceUpdate;
        }
        return result;
    }

    /**
     * @override
     */
    makeFilterDynamic(filterInfo, previousFilter, fieldName, rawFilter, rawColors) {
        return {
            ...super.makeFilterDynamic(filterInfo, previousFilter, fieldName, rawFilter, rawColors),
            resourceType: rawFilter['resourceType'],
            colorIndex: rawFilter['colorIndex'],
        };
    }

    /**
     * @override
     */
    makeContextDefaults(rawRecord) {
        const context = super.makeContextDefaults(...arguments);
        if (["day", "week"].includes(this.meta.scale)) {
            context['planning_keep_default_datetime'] = true;
        }
        return context;
    }

    /**
     * @override
     */
    getAllDayDates(start, end) {
        if (end) {
            return [start.startOf("day"), end.endOf("day")];
        }
        return [start.startOf("day"), start.endOf("day")];
    }

    /**
     * @override
     */
    async multiCreateRecords(multiCreateData, dates) {
        if (!dates.length) {
            await this.load();
            return [];
        }
        const values = await multiCreateData.record.getChanges();
        if (values.template_id) {
            const schedule = await this.orm.read("planning.slot.template", [values['template_id']], ["start_time", "end_time", "duration_days"]);
            const records = [];
            const [section] = this.filterSections;
            for (const date of dates) {
                const rawRecord = this.buildRawRecord({ start: date }, { 'batch_create_calendar': true, 'schedule': schedule });
                for (const filter of section.filters) {
                    if (filter.active && filter.type === "record") {
                        let sectionFieldValue = filter.value;
                        const sectionField = this.meta.fields[section.fieldName];
                        if (sectionField && sectionFieldValue && ['one2many', 'many2many'].includes(sectionField.type)) {
                            sectionFieldValue = [sectionFieldValue];
                        }
                        records.push({
                            ...rawRecord,
                            ...values,
                            [section.fieldName]: sectionFieldValue,
                        });
                    }
                }
            }
            if (records.length) {
                const createdRecords = await this.orm.call(this.meta.resModel, "create_batch_from_calendar", [records]);
                await this.load();
                return createdRecords
            }
            return [];
        }
    }

    /**
    * @override
    */
    fetchFilters(resModel, fieldNames) {
        return this.orm.call(resModel, "get_calendar_filters", [[], user.userId, fieldNames]);
    }

    /**
     * @override
     */
    makeFilterRecord(filterInfo, previousFilter, rawRecord) {
        let filterRecord = super.makeFilterRecord(...arguments);
        if (!filterRecord.value) {
            filterRecord.canRemove = false;
            filterRecord.label = _t("Open Shifts");
        }
        // We need the resource type to display the correct icon in the filter section in the side panel
        filterRecord.resourceType = rawRecord.resource_type;
        return filterRecord;
    }

    /*
    * @override
    */
    async loadFilters(data) {
        const loadedFilters = await super.loadFilters(data);
        if (!Object.keys(this.data.filterSections).length && loadedFilters.sections.resource_ids?.filters) {
            // This is the first load of the view, we set the 'open shifts' filter to active
            loadedFilters.sections.resource_ids.filters[0].active = true;
        }
        return loadedFilters;
    }

    /**
     * @override
     */
    computeEventsToScheduleDomain(data) {
        const { date_start, date_stop } = this.meta.fieldMapping;
        let baseDomain = this.getBaseDomain();

        const resourcesDomain = new Domain(baseDomain)
            .toList()
            .some(
                (leaf) =>
                    Array.isArray(leaf) &&
                    leaf.length === 3 &&
                    ["resource_ids", "department_id", "manager_id", "user_ids"].includes(leaf[0])
            );
        baseDomain = resourcesDomain
            ? Domain.or([baseDomain, [["resource_ids", "=", false]]])
            : baseDomain;

        const domain = Domain.removeDomainLeaves(
            Domain.and([baseDomain, this.computeFiltersDomain(data)]),
            [date_start, date_stop]
        );
        if (date_start === date_stop) {
            return Domain.and([domain, [[date_start, "=", false]]]);
        }
        return Domain.and([
            domain,
            Domain.and([[[date_start, "=", false]], [[date_stop, "=", false]]]),
        ]);
    }

    /**
     * @override
     */
    _getScheduleContext() {
        return {
            ...super._getScheduleContext(...arguments),
            add_materials_assigned_to_employees: true,
            default_end_datetime: serializeDateTime(this.meta.date.endOf(this.scale)),
            scale: this.scale,
        };
    }

    /**
     * @override
     */
    _getScheduleData(date) {
        const data = super._getScheduleData(date);
        const resource_ids = (this.data.filterSections.resource_ids?.filters || [])
            .filter((f) => f.active && f.value)
            .map((f) => f.value);
        data.resource_ids = resource_ids.length ? resource_ids : false;
        return data;
    }

    /**
     * @override
     */
    _getUnscheduleContext() {
        return {
            ...super._getUnscheduleContext(...arguments),
            from_slot_unscheduling: true,
        };
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
        const records = this.data.records;
        if (eventId in records) {
            data.allocated_hours = records[eventId].rawRecord.allocated_hours;
        }
        return data;
    }

    /**
     * @override
     */
    async scheduleEvent(eventId, date) {
        const result = await this.orm.call(
            this.meta.resModel,
            "assign_slot",
            [[eventId], this._getScheduleData(date)],
            { context: this._getScheduleContext() }
        );
        await this.load();
        return result;
    }
}
