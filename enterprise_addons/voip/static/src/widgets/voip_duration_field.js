import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatDuration } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function voipFormatDuration(value) {
    return formatDuration({ seconds: value }, { showSeconds: true, unit: "seconds" });
}

export class VoipDurationField extends Component {
    static template = "voip.VoipDurationField";

    props = useProps(standardFieldProps);

    get formattedValue() {
        const value = this.props.record.data[this.props.name];
        return voipFormatDuration(value);
    }
}

export const voipDurationField = {
    component: VoipDurationField,
    displayName: _t("VoIP Duration"),
    supportedTypes: ["integer"],
};

registry.category("fields").add("voip_duration", voipDurationField);
registry.category("formatters").add("voip_duration", voipFormatDuration);
