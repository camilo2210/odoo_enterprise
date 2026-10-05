import { registry } from "@web/core/registry";
import { formatDateTime } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

import { Component, useProps } from "@odoo/owl";
import { formatList } from "@web/core/l10n/utils";
import { _t } from "@web/core/l10n/translation";

export class ConflictingSlotIdsField extends Component {
    static template = "planning.ConflictingSlotIdsField";

    props = useProps(standardFieldProps);

    setup() {
        this.actionService = useService("action");
    }

    get conflictingSlots() {
        return this.props.record.data[this.props.name].records;
    }

    get conflictString() {
        let slots = this.conflictingSlots;
        if (slots.length > 1) {
            slots = [slots[0]];
            slots.push({ data: { display_name: _t("other ones.") }})
        }
        return formatList(slots.map((slot) => {
            let displayName = slot.data.display_name;
            const startDatetime = slot.data.start_datetime;
            const endDatetime = slot.data.end_datetime;
            if (displayName && startDatetime && endDatetime) {
                let showDate = true;
                const showTime = true;
                const showSeconds = false;
                if (startDatetime.hasSame(endDatetime, "day")) {
                    showDate = false;
                }
                return _t("%(display_name)s (%(start_datetime)s - %(end_datetime)s)", {
                    display_name: displayName,
                    start_datetime: formatDateTime(startDatetime, {
                        showTime,
                        showDate,
                        showSeconds
                    }),
                    end_datetime: formatDateTime(endDatetime, {
                        showTime,
                        showDate,
                        showSeconds
                    }),
                })
            }
            return displayName;
        }));
    }

    async showConflictedSlots() {
        if (this.props.record.isNew) {
            await this.props.record.save({ noReload: true });
        }
        this.actionService.doActionButton({
            type: "object",
            resId: this.props.record.resId,
            name: "action_see_overlaping_slots",
            resModel: "planning.slot",
        });
    }
}

export const conflictingSlotIdsField = {
    component: ConflictingSlotIdsField,
    supportedTypes: ["many2many"],
    additionalClasses: ["d-inline-flex align-items-center"],
    relatedFields: () => {
        return [
            { name: "display_name", type: "char" },
            { name: "start_datetime", type: "datetime" },
            { name: "end_datetime", type: "datetime" },
        ];
    },
};

registry.category("fields").add("conflicting_slot_ids", conflictingSlotIdsField);
