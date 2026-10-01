import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, t, useProps } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";

export class SimpleDateTimeField extends Component {
    static template = "voip.SimpleDateTimeField";

    props = useProps({
        ...standardFieldProps,
        durationField: t.string().optional(),
    });

    setup() {
        this.store = useService("mail.store");
    }

    get formattedDate() {
        const dt = this.props.record.data[this.props.name];
        if (!dt) {
            return "";
        }
        const startOfToday = this.store.startOfToday;
        const time = dt.toLocaleString({ hour: "numeric", minute: "2-digit" });

        let dateStr;
        if (dt.hasSame(startOfToday, "day")) {
            dateStr = _t("Today, %(time)s", { time });
        } else {
            const yesterday = startOfToday.minus({ days: 1 });
            if (dt.hasSame(yesterday, "day")) {
                dateStr = _t("Yesterday, %(time)s", { time });
            } else {
                dateStr = dt.toLocaleString({
                    month: "numeric",
                    day: "2-digit",
                    year: "2-digit",
                    hour: "numeric",
                    minute: "2-digit",
                });
            }
        }
        const durationField = this.props.durationField;
        if (durationField) {
            const duration = this.props.record.data[durationField];
            if (duration) {
                return _t("%(date)s (%(duration)s)", { date: dateStr, duration });
            }
        }
        return dateStr;
    }
}

export const simpleDateTimeField = {
    component: SimpleDateTimeField,
    displayName: _t("Simple Date & Time"),
    supportedTypes: ["datetime"],
    extractProps: ({ attrs, options }) => ({
        durationField: options.duration_field,
    }),
};

registry.category("fields").add("voip_simple_datetime", simpleDateTimeField);
