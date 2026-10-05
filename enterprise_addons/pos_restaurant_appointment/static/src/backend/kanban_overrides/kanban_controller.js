/* global posmodel */

import { PosKanbanController } from "@pos_appointment/app/kanban_extend/kanban_controller";
import { patch } from "@web/core/utils/patch";

patch(PosKanbanController.prototype, {
    get totalAvailableCapacity() {
        const groupWithRecords = this.model.root.groups.find(
            (group) => group.list?.records?.length
        );
        return posmodel.getTotalAvailableCapacity(groupWithRecords?.list.records);
    },
});
