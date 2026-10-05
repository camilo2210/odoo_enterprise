import { PosAccessRightPlugin } from "@point_of_sale/app/plugins/access_right_plugin";
import { patch } from "@web/core/utils/patch";
import { localeCompare } from "@web/core/l10n/utils";
import { getTimeUtil } from "@point_of_sale/utils";

const { DateTime } = luxon;

patch(PosAccessRightPlugin.prototype, {
    getCashierSelectionList(employees) {
        const list = super.getCashierSelectionList(employees);
        const existingSlot = this.data.models["planning.slot"].length;
        if (!existingSlot) {
            return list;
        }

        const planningList = this.preparePlanningList();
        for (const emp of list) {
            if (!planningList[emp.resource_id?.id]) {
                continue;
            }

            emp.subtitle = planningList[emp.resource_id.id];
        }

        const currentCashierId = this.loggedCashier?.id;
        if (currentCashierId && planningList[currentCashierId]) {
            this.loggedCashier.subtitle = planningList[currentCashierId];
        }

        // Items with subtitle first, then alphabetical order
        return list.sort((a, b) => {
            if (a.subtitle && !b.subtitle) {
                return -1;
            }
            if (!a.subtitle && b.subtitle) {
                return 1;
            }
            return localeCompare(a.name, b.name);
        });
    },

    preparePlanningList() {
        const dateNow = DateTime.now();
        const slots = this.data.models["planning.slot"].filter((slot) => {
            const slotStart = slot.start_datetime;
            const slotEnd = slot.end_datetime;
            return (
                (slotStart <= dateNow && slotEnd >= dateNow) || dateNow.hasSame(slotStart, "day")
            );
        });

        return slots.reduce((acc, slot) => {
            for (const resource of slot.resource_ids || []) {
                if (resource.id) {
                    acc[resource.id] = `Planning: ${getTimeUtil(
                        slot.start_datetime
                    )} - ${getTimeUtil(slot.end_datetime)}`;
                }
            }
            return acc;
        }, {});
    },
});
