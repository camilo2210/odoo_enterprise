import { onWillStart, onWillUnmount } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { pick } from "@web/core/utils/objects";

export class PlanningFieldServiceRouting {
    constructor({ getGeolocation, getRecords, getResourceWorkLocations }) {
        this.getGeolocation = getGeolocation;
        this.getRecords = getRecords;
        this.getResourceWorkLocations = getResourceWorkLocations;
        this.notification = useService("notification");
        this.orm = useService("orm");

        onWillStart(async () => {
            this.isManager = await user.hasGroup("planning.group_planning_manager");
        });
        onWillUnmount(() => {
            const geolocation = this.getGeolocation();
            if (geolocation) {
                geolocation.stopFetchingCoordinates();
            }
        });
    }

    /**
     * Computes the travel times as daily paths per resource.
     *
     * @param {boolean} [reschedule] whether to reschedule the shifts to take into account travel times
     * @param {Set<Number> | null} [resourceIds] resources for which to compute the travel times
     *
     * @returns boolean whether the travel times were correctly computed and updated server-side.
     */
    async computeTravelTimes(reschedule = false, resourceIds = null) {
        if (!this.isManager) {
            return false;
        }

        const geolocation = this.getGeolocation();
        const records = this.getRecords();
        const resourceWorkLocations = this.getResourceWorkLocations();
        if (
            !geolocation ||
            !geolocation.useMapBoxAPI ||
            !records.length ||
            !Object.keys(resourceWorkLocations).length
        ) {
            return false;
        }

        const recordGroups = this._getRecordsByResource(records);
        const resourceEntries = Object.entries(recordGroups).filter(([resourceId, records]) =>
            resourceIds
                ? resourceIds.has(parseInt(resourceId))
                : records.some((r) => !r.travel_times_up_to_date)
        );
        if (!resourceEntries.length) {
            return false;
        }
        const processedRecords = resourceEntries.flatMap(([, records]) => records);

        await geolocation.geolocatePartners(processedRecords.map((r) => r.partner_id));

        // Reset fields before computing
        processedRecords.forEach((r) => {
            r.travel_time_in = 0;
            r.travel_time_out = 0;
            r.travel_distance_in = 0;
            r.travel_distance_out = 0;
        });

        const promises = resourceEntries.map(async ([resourceId, records]) => {
            const resourceDailyPath = records
                .map((r) => r.partner_id)
                .filter((p) => p.partner_latitude && p.partner_longitude);

            if (!resourceDailyPath.length) {
                return;
            }

            // Technician's day starts and ends from the work location
            const workLocation = resourceWorkLocations[resourceId];
            const coordinates = [workLocation, ...resourceDailyPath, workLocation].map((p) => ({
                latitude: p.partner_latitude,
                longitude: p.partner_longitude,
            }));

            const route = await geolocation.fetchRoute(coordinates, "ordered");
            if (!route) {
                return;
            }

            records.forEach((record, idx) => {
                const routeIn = route.legs[idx];
                record.travel_time_in = Math.max(record.travel_time_in, routeIn.duration / 3600);
                record.travel_distance_in = Math.max(
                    record.travel_distance_in,
                    routeIn.distance / 1000
                );

                const routeOut = route.legs[idx + 1];
                record.travel_time_out = Math.max(record.travel_time_out, routeOut.duration / 3600);
                record.travel_distance_out = Math.max(
                    record.travel_distance_out,
                    routeOut.distance / 1000
                );
            });
        });
        await Promise.all(promises);
        this._updateSlotTravelTimes(processedRecords, reschedule);
        return true;
    }

    async _updateSlotTravelTimes(records, reschedule) {
        if (!this.isManager || !records.length) {
            return {};
        }
        records.forEach((r) => (r.travel_times_up_to_date = true));
        const recordsToCache = records.map((r) =>
            pick(
                r,
                "id",
                "travel_time_in",
                "travel_time_out",
                "travel_distance_in",
                "travel_distance_out"
            )
        );
        await this.orm.call("planning.slot", "update_slot_travel_times", [
            recordsToCache,
            reschedule,
        ]);
    }

    _getRecordsByResource(records) {
        const recordsByResource = {};
        for (const record of records) {
            for (const resourceId of record.resource_ids) {
                if (!recordsByResource[resourceId]) {
                    recordsByResource[resourceId] = [];
                }
                recordsByResource[resourceId].push(record);
            }
        }
        return recordsByResource;
    }
}

export function usePlanningFieldServiceRouting() {
    return new PlanningFieldServiceRouting(...arguments);
}
