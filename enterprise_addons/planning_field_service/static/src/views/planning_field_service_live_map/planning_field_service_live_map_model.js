import { parseDateTime } from "@web/core/l10n/dates";
import { PlanningFieldServiceMapModel } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_model";

const { DateTime } = luxon;

export class PlanningFieldServiceLiveMapModel extends PlanningFieldServiceMapModel {
    static services = [...PlanningFieldServiceMapModel.services, "field_service_geolocation"];

    setup(params, services) {
        super.setup(...arguments);
        this.fieldServiceGeolocation = services.field_service_geolocation;
    }

    _getGroupOriginAddress(groupId) {
        if (this.data.groupByKey !== "resource_ids" || !groupId) {
            return super._getGroupOriginAddress(groupId);
        }
        const resource = this.data.allRecordGroups[groupId].records[0].resource_ids.find(
            (r) => r.id == groupId
        );
        if (!resource) {
            return super._getGroupOriginAddress(groupId);
        }
        const resourceToLocate = resource.assigned_employee_id
            ? resource.assigned_employee_id.resource_id
            : resource.id;
        const locatedResource = this.data.locatedResources.find((r) => r.id == resourceToLocate);

        return locatedResource
            ? locatedResource.address.join(", ")
            : super._getGroupOriginAddress(groupId);
    }

    /**
     * @override
     * @protected
     */
    _shouldUpdateRoutes() {
        return false;
    }

    async _fetchLocatedResources(data) {
        data.locatedResources = [];
        const records = await this.orm.searchRead(
            "resource.resource",
            [
                ["live_latitude", "!=", false],
                ["live_longitude", "!=", false],
                ["live_location_last_update", "!=", false],
            ],
            ["live_latitude", "live_longitude", "live_location_last_update", "display_name"]
        );
        return Promise.all(
            records.map(async (r) => {
                const address = await this.geolocation.searchAddressFromCoordinates(
                    r.live_latitude,
                    r.live_longitude
                );
                r.address = this._formatAddress(address);
                data.locatedResources.push(r);
                this._notifyFetchedCoordinate(data);
            })
        );
    }

    async _fetchPartnersGeolocation(metaData, data) {
        return Promise.all([
            super._fetchPartnersGeolocation(metaData, data),
            this._fetchLocatedResources(data),
        ]);
    }

    _getRecordSpecification(metaData, data) {
        const specification = super._getRecordSpecification(metaData, data);
        const fieldsToAdd = {
            assigned_employee_id: {
                fields: { resource_id: {} },
            },
        };
        if (specification.resource_ids) {
            Object.assign(specification.resource_ids.fields, fieldsToAdd);
        }
        return specification;
    }

    /**
     * This override is necessary because if the navigator has a watch running for the
     * user position (i.e., through `navigator.geolocation.watchPosition`), any call to
     * `navigator.geolocation.getCurrentPosition` never resolves.
     * @override
     */
    async _setUserPosition(data) {
        if (!this.fieldServiceGeolocation.isWatchRunning) {
            return super._setUserPosition(data);
        }
        data.userPosition = this.fieldServiceGeolocation.currentPosition;
        return data;
    }

    async _getRecordGroups(metaData, data) {
        const groups = await super._getRecordGroups(metaData, data);
        if (data.groupByKey !== "resource_ids") {
            return groups;
        }
        const now = DateTime.now();
        for (const [id, { records }] of Object.entries(groups)) {
            const shift = records.find((r) => {
                const start = parseDateTime(r.start_datetime);
                const end = parseDateTime(r.end_datetime);
                return (start <= now && now <= end) || start > now;
            });
            groups[id].records = shift ? [shift] : [];
        }
        data.records = Object.values(groups).flatMap((g) => g.records);
        return groups;
    }

    _getGroupSourcePosition(data, groupByKey, groupId) {
        let resource;
        if (
            groupByKey !== "resource_ids" ||
            !(resource = data.locatedResources.find((r) => r.id == groupId))
        ) {
            return {};
        }
        return {
            longitude: resource.live_longitude,
            latitude: resource.live_latitude,
        };
    }

    _getGroupDestinationPosition(data, groupByKey, groupId) {
        return {};
    }

    /**
     * @protected
     */
    _formatAddress(address) {
        const { street, house_number, zip, city } = address;
        return [
            [street, house_number].filter(Boolean).join(", "),
            [zip, city].filter(Boolean).join(" "),
        ];
    }
}
