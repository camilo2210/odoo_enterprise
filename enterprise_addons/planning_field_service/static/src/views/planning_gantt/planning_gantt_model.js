import { compareDatetime } from "@mail/utils/common/misc";
import { patch } from "@web/core/utils/patch";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";

import { PlanningGanttModel } from "@planning/views/planning_gantt/planning_gantt_model";

import { usePlanningFieldServiceRouting } from "../planning_hooks";
import { _t } from "@web/core/l10n/translation";

patch(PlanningGanttModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.geolocation = new Geolocation();
        this.routing = usePlanningFieldServiceRouting({
            getGeolocation: () => this.geolocation,
            getRecords: () =>
                this.data.records
                    .filter((r) => r.partner_id && r.resource_ids.length)
                    .sort((a, b) =>
                        compareDatetime(
                            a[this.metaData.dateStartField],
                            b[this.metaData.dateStartField]
                        )
                    ),
            getResourceWorkLocations: () => this.data.resourceWorkLocations,
        });
    },
    get canUpdateTravelTimes() {
        return (
            this.isManager &&
            !!this.metaData.bufferStartField &&
            !!this.metaData.bufferStopField &&
            this.metaData.rangeId === "day" &&
            this.metaData.groupedBy.includes("resource_ids") &&
            this.geolocation.useMapBoxAPI
        );
    },
    get shouldComputeTravelTimesOnLoad() {
        return this.data.records
            .filter((r) => r.partner_id && r.resource_ids.length && r.start_datetime)
            .every((r) => !r.travel_times_up_to_date);
    },
    get shouldUpdateTravelTimes() {
        return this.data.records
            .filter((r) => r.partner_id && r.resource_ids.length && r.start_datetime)
            .some((r) => !r.travel_times_up_to_date);
    },
    get notifyOnTravelTimesUpdate() {
        return true;
    },
    async updateTravelTimes() {
        const success = await this.keepLast.add(this._updateTravelTimes());
        if (success && this.notifyOnTravelTimesUpdate) {
            this.notification.add(_t("Travel times updated"), {
                type: "success",
            });
        }
        return success;
    },
    async _updateTravelTimes(reschedule, resourceIds) {
        const success = await this.routing.computeTravelTimes(reschedule, resourceIds);
        if (success) {
            this.notify();
        }
        return success;
    },
    /**
     * @override
     */
    _processGanttData(metaData, data, ganttData) {
        if ("resource_work_locations" in ganttData) {
            data.resourceWorkLocations = ganttData.resource_work_locations;
        }
        super._processGanttData(metaData, data, ganttData);
    },
    /**
     * @override
     */
    _getRecordSpecification(metaData) {
        const specification = super._getRecordSpecification(metaData);
        if (specification.partner_id) {
            Object.assign(specification.partner_id.fields, {
                contact_address_complete: {},
                partner_latitude: {},
                partner_longitude: {},
            });
        }
        return {
            ...specification,
            travel_time_in: {},
            travel_distance_in: {},
            travel_time_out: {},
            travel_distance_out: {},
            travel_times_up_to_date: {},
            break_time: {},
        };
    },
    /**
     * @override
     */
    async _fetchData(metaData, additionalContext) {
        await super._fetchData(metaData, additionalContext);
        if (this.canUpdateTravelTimes && this.shouldComputeTravelTimesOnLoad) {
            await this._updateTravelTimes();
        }
    },
    /**
     * @override
     */
    getSchedule(params = {}) {
        const result = super.getSchedule(params);
        const fieldNames = [
            this.metaData.bufferStartField,
            this.metaData.bufferStopField,
            "travel_distance_in",
            "travel_distance_out",
            "travel_times_up_to_date",
        ];
        for (const fieldName of fieldNames) {
            if (params[fieldName]) {
                result[fieldName] = params[fieldName];
            }
        }
        return result;
    },
});
