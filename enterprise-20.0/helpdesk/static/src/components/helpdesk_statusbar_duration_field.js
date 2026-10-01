import { formatDuration } from "@web/core/l10n/dates";

import {
    RottingStatusBarDurationField,
    rottingStatusBarDurationField,
} from "@mail/js/rotting_mixin/rotting_statusbar";

import { registry } from "@web/core/registry";

export class HelpdeskStatusBarDurationField extends RottingStatusBarDurationField {
    getAllItems() {
        const items = super.getAllItems();
        const tracking = this.props.record.data.duration_stage_tracking || {};
        if (tracking) {
            for (const item of items) {
                const duration = tracking[item.value] || 0;
                if (duration > 0) {
                    item.shortTimeInStage = formatDuration(duration * 60, false);
                    item.fullTimeInStage = formatDuration(duration * 60, true);
                }
            }
        }

        return items;
    }
}

export const helpdeskRottingStatusBarDurationField = {
    ...rottingStatusBarDurationField,
    component: HelpdeskStatusBarDurationField,
    fieldDependencies: [
        ...rottingStatusBarDurationField.fieldDependencies,
        { name: "duration_stage_tracking", type: "JSON" },
    ],
};

registry
    .category("fields")
    .add("helpdesk_rotting_statusbar_duration", helpdeskRottingStatusBarDurationField);
