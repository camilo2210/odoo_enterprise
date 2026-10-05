import { usePlugin } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";

import { PlanningFieldServiceMapModel } from "@planning_field_service/views/planning_field_service_map/planning_field_service_map_model";

import { MapTimelineCommunicationPlugin } from "./map_timeline_communication_plugin/planning_field_service_map_timeline_communication_plugin";

import { getOpenShiftsDomain } from "./planning_field_service_map_timeline_domains";

export class PlanningFieldServiceMapTimelineModel extends PlanningFieldServiceMapModel {
    communication = usePlugin(MapTimelineCommunicationPlugin);

    /**
     * @override
     */
    async _fetchData(metaData) {
        const data = await super._fetchData(metaData);
        if (this.preserveMapPosition) {
            data.shouldUpdatePosition = false;
            this.preserveMapPosition = false;
        }
        return data;
    }

    /**
     * @override
     */
    _getRecordDomain(metaData) {
        const domainWithoutDates = Domain.removeDomainLeaves(metaData.domain, [
            "start_datetime",
            "end_datetime",
        ]).toList();
        const dateDomain = ["&", ["start_datetime", "=", false], ["end_datetime", "=", false]];
        const openShiftsDomain = getOpenShiftsDomain(metaData.domain);
        const shiftsToScheduleDomain = Domain.and([domainWithoutDates, dateDomain]);
        const openShiftsToScheduleDomain = Domain.and([
            getOpenShiftsDomain(domainWithoutDates),
            dateDomain,
        ]);
        return Domain.and([
            Domain.or([
                metaData.domain.length ? metaData.domain : Domain.TRUE.toList(),
                openShiftsDomain,
                shiftsToScheduleDomain,
                openShiftsToScheduleDomain,
            ]),
            [["partner_id", "!=", false]],
        ]).toList();
    }

    /**
     * @override
     */
    async _getRecordGroups(metaData, data) {
        const groups = await super._getRecordGroups(metaData, data);

        // A record with several resource_ids appears in each of their groups,
        // so it must be de-duplicated by id when collected here, or it would
        // be listed more than once under "Shifts to Schedule".
        const shiftsToSchedule = new Map();
        for (const [groupId, group] of Object.entries(groups)) {
            for (const record of group.records) {
                if (!record.start_datetime) {
                    shiftsToSchedule.set(record.id, record);
                }
            }
            groups[groupId].records = group.records.filter((r) => r.start_datetime);
        }

        groups[this.shiftsToScheduleGroupId] = {
            name: this.shiftsToScheduleGroupId,
            records: [...shiftsToSchedule.values()],
        };

        return groups;
    }

    get shiftsToScheduleGroupId() {
        return _t("Shifts to Schedule");
    }

    /**
     * @override
     */
    toggleGroup(groupId) {
        super.toggleGroup(groupId);
        const closedGroupIds = this.closedGroupIds();

        // When folding "Open Shifts" group from the map, we want to fold the falsy row (Open Shifts) in the gantt
        const openShiftsGroupId = this.metaData.fields.resource_ids.falsy_value_label;
        const foldedRowIds = new Set(closedGroupIds);
        if (foldedRowIds.delete(openShiftsGroupId)) {
            foldedRowIds.add("false");
        }
        this.communication.setFoldedGroups(foldedRowIds);

        // When folding "Shifts to Schedule" group from the map, we want to hide the gantt side panel
        this.communication.setShiftsToScheduleFolded(
            closedGroupIds.has(this.shiftsToScheduleGroupId)
        );
    }
}
