import { usePlugin } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { orderByToString } from "@web/search/utils/order_by";

import { PlanningGanttModel } from "@planning/views/planning_gantt/planning_gantt_model";

import { MapTimelineCommunicationPlugin } from "../map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";
import { getOpenShiftsDomain } from "../planning_field_service_map_timeline_domains";

export class MapTimelineGanttModel extends PlanningGanttModel {
    communication = usePlugin(MapTimelineCommunicationPlugin);

    /**
     * @override
     */
    _getDomain(metaData) {
        const { dateStartField, dateStopField, globalStart, globalStop } = metaData;
        const domainWithoutDates = Domain.removeDomainLeaves(this.searchParams.domain, [
            dateStartField,
            dateStopField,
        ]).toList();
        const openShiftsDomain = getOpenShiftsDomain(domainWithoutDates);
        // We want to filter like this: (searchDomain OR openShiftsDomain) AND dateRangeDomain.
        const searchDomain = domainWithoutDates.length ? domainWithoutDates : Domain.TRUE.toList();
        const domain = Domain.and([
            Domain.or([searchDomain, openShiftsDomain]),
            [
                "&",
                [
                    dateStartField,
                    "<",
                    this.dateStopFieldIsDate(metaData)
                        ? serializeDate(globalStop)
                        : serializeDateTime(globalStop),
                ],
                [
                    dateStopField,
                    this.dateStartFieldIsDate(metaData) ? ">=" : ">",
                    this.dateStartFieldIsDate(metaData)
                        ? serializeDate(globalStart)
                        : serializeDateTime(globalStart),
                ],
            ],
        ]);
        return domain.toList();
    }

    /**
     * @override
     */
    _getEventsToScheduleDomain(metaData) {
        const { dateStartField, dateStopField } = metaData;
        // The day filter shouldn't hide shifts to schedule, since those have no date.
        const baseDomain = Domain.removeDomainLeaves(this.searchParams.domain, [
            dateStartField,
            dateStopField,
        ]).toList();
        const openShiftsDomain = getOpenShiftsDomain(baseDomain);
        const searchDomain = baseDomain.length ? baseDomain : Domain.TRUE.toList();
        const domain = Domain.and([
            Domain.or([searchDomain, openShiftsDomain]),
            ["&", [dateStartField, "=", false], [dateStopField, "=", false]],
        ]);
        return domain.toList();
    }

    /**
     * @override
     */
    _getEventsToScheduleOrder() {
        return orderByToString(this.searchParams.context.shiftsToScheduleOrder || []);
    }

    /**
     * @override
     */
    async load(searchParams) {
        // This Gantt has no controls of its own — only the search filter can
        // move it. But load() derives the visible window once, ever, so
        // without this reset it would freeze on the range it first loaded with.
        this.metaData.startDate = this.metaData.stopDate = undefined;
        return super.load(searchParams);
    }

    /**
     * @override
     */
    async fetchData() {
        await super.fetchData(...arguments);
        this.communication.notify();
    }

    /**
     * @override
     */
    get shouldComputeTravelTimesOnLoad() {
        return true;
    }

    /**
     * @override
     */
    get notifyOnTravelTimesUpdate() {
        return false;
    }
}
