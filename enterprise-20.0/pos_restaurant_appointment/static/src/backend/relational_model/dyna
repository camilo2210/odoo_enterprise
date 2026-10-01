/* global posmodel */

import { patch } from "@web/core/utils/patch";
import { DynamicGroupList } from "@web/model/relational_model/dynamic_group_list";

patch(DynamicGroupList.prototype, {
    async moveRecords(recordIds, refId, targetGroupId) {
        const targetGroup = this.groups.find((g) => g.id === targetGroupId);
        // the appointments that change status, i.e. the ones not already in the target group
        const movedRecords = this.records.filter(
            (r) => recordIds.includes(r.id) && r.group !== targetGroup
        );
        const newValue = targetGroup?.value;
        const fieldName = targetGroup?.groupByField.name;

        const result = await super.moveRecords(recordIds, refId, targetGroupId);

        // Show notification when appointment is moved to attended stage
        if (posmodel && fieldName === "appointment_status" && newValue === "attended") {
            for (const record of movedRecords) {
                if (record.data.appointment_type_schedule_based_on === "resources") {
                    const assignedResources = record.data.resource_ids.records;
                    posmodel.showResourceAssignNotification(record, assignedResources, {
                        viewMode: "kanban",
                    });
                }
            }
        }
        return result;
    },
});
