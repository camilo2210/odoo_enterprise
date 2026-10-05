import { MapModel } from "@web_map/map_view/map_model";

export class PlanningFieldServiceMapModel extends MapModel {
    /**
     * Material resources are folded by default.
     *
     * @override
     */
    _getDefaultClosedGroupIds(data) {
        if (data.groupByKey !== "resource_ids") {
            return super._getDefaultClosedGroupIds(data);
        }
        const materialResourceIds = new Set();
        for (const record of data.records) {
            for (const resource of record.resource_ids) {
                if (resource.resource_type === "material") {
                    materialResourceIds.add(String(resource.id));
                }
            }
        }
        return materialResourceIds;
    }

    /**
     * @override
     */
    _getRecordSpecification(metaData, data) {
        const specification = super._getRecordSpecification(metaData, data);
        if (specification.resource_ids) {
            Object.assign(specification.resource_ids.fields, {
                resource_type: {},
                color: {},
            });
        }
        return specification;
    }
}
