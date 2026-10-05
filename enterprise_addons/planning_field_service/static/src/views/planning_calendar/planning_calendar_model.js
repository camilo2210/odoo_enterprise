import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";
import { PlanningCalendarModel } from "@planning/views/planning_calendar/planning_calendar_model";
import { unique } from "@web/core/utils/arrays";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";

patch(PlanningCalendarModel.prototype, {
    setup(params, services) {
        const extraFields = [
            // fields needed for the Start button
            "can_edit",
            "partner_id",
            "state",
            "user_ids",
            // fields needed for the map navigation button
            "partner_city",
            "partner_country_id",
        ];
        params.fieldNames = unique(params.fieldNames.concat(extraFields));
        super.setup(params, services);

        this.geolocation = new Geolocation();
    },

    /**
     * @override
     */
    getBaseDomain() {
        const baseDomain = super.getBaseDomain();
        const openShiftsFilter = this.data?.filterSections?.resource_ids?.filters.find(
            (f) => f.value === false
        );
        if (openShiftsFilter?.active === false) {
            return baseDomain;
        }
        const hasResourceFilter = baseDomain.some(
            (leaf) =>
                Array.isArray(leaf) &&
                leaf.length === 3 &&
                ["resource_ids", "department_id", "manager_id"].includes(leaf[0])
        );
        if (!hasResourceFilter) {
            return baseDomain;
        }
        const openShiftsDomain = baseDomain.map((leaf) =>
            Array.isArray(leaf) &&
            leaf.length === 3 &&
            ["resource_ids", "department_id", "manager_id"].includes(leaf[0])
                ? ["resource_ids", "=", false]
                : leaf
        );
        return Domain.or([new Domain(baseDomain), new Domain(openShiftsDomain)]).toList();
    },

    /**
     * @override
     */
    get canEdit() {
        return this.isManager && super.canEdit;
    },

    /**
     * @override
     */
    async loadDynamicFilterSection(data, fieldName, filterInfo, previousSection) {
        const result = await super.loadDynamicFilterSection(
            data,
            fieldName,
            filterInfo,
            previousSection
        );
        const hasOpenShifts = Object.values(data.records).some(
            (r) => !r.rawRecord.resource_ids?.length
        );
        const hasResourceDomainFilter = this.getBaseDomain().some(
            (leaf) =>
                Array.isArray(leaf) &&
                leaf.length === 3 &&
                ["resource_ids", "department_id", "manager_id"].includes(leaf[0])
        );
        if (
            fieldName === "resource_ids" &&
            (hasOpenShifts || hasResourceDomainFilter) &&
            !result.filters.some((f) => f.value === false)
        ) {
            const previousFilters = previousSection ? previousSection.filters : [];
            const previousOpenShiftsFilter = previousFilters.find((f) => f.value === false);
            result.filters.unshift(
                this.makeFilterDynamic(
                    filterInfo,
                    previousOpenShiftsFilter,
                    fieldName,
                    { id: false, [fieldName]: false, resourceType: false, colorIndex: null },
                    []
                )
            );
        }
        return result;
    },

    /**
     * @override
     */
    async loadRecords(data) {
        const records = await super.loadRecords(data);
        this._openShiftRecords = Object.fromEntries(
            Object.entries(records).filter(([, r]) => !r.rawRecord.resource_ids?.length)
        );
        return records;
    },

    /**
     * @override
     */
    async updateData(data) {
        this._openShiftRecords = null;
        await super.updateData(...arguments);
        const openShiftsFilter = data.filterSections.resource_ids?.filters.find(
            (f) => f.value === false
        );
        if (openShiftsFilter?.active && this._openShiftRecords) {
            Object.assign(data.records, this._openShiftRecords);
            this._openShiftRecords = null;
        }
    },

    /**
     * @override
     */
    computeEventsToScheduleDomain(data) {
        const openShiftsFilter = this.data.filterSections.resource_ids?.filters.find(
            (f) => f.value === false
        );
        const baseDomain = super.computeEventsToScheduleDomain(data);
        if (openShiftsFilter && !openShiftsFilter.active) {
            return Domain.and([baseDomain, [["resource_ids", "!=", false]]]);
        }
        return baseDomain;
    },

    /**
     * @override
     */
    _getScheduleData(date) {
        return {
            ...super._getScheduleData(date),
            resource_ids: false,
        };
    },
});
