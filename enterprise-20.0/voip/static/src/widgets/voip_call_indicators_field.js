import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { mergeClasses } from "@web/core/utils/classname";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class VoipCallIndicatorsField extends Component {
    static template = "voip.VoipCallIndicatorsField";

    props = useProps(standardFieldProps);

    get icons() {
        return [
            {
                label: _t("Recording"),
                name: "graphic_eq",
                classes: mergeClasses("text-muted", {
                    invisible: !this.props.record.data.has_recording,
                }),
            },
        ];
    }
}

export const voipCallIndicatorsField = {
    component: VoipCallIndicatorsField,
    displayName: _t("VoIP Call Indicators"),
};

registry.category("fields").add("voip_call_indicators", voipCallIndicatorsField);
