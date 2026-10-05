import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class VoipX2ManyRequirementField extends X2ManyField {
    setup() {
        super.setup();
        const originalOpenRecord = this._openRecord;
        this._openRecord = (params) => {
            const title = params.record
                ? params.record.data.name || _t("Regulatory Requirement")
                : _t("Create Regulatory Requirement");
            originalOpenRecord({ ...params, title });
        };
    }
}

export const voipX2ManyRequirementField = {
    ...x2ManyField,
    component: VoipX2ManyRequirementField,
};

registry.category("fields").add("voip_x2many_requirement_ids", voipX2ManyRequirementField);
