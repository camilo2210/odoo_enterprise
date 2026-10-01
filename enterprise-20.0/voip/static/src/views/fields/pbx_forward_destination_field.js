import { t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useRecordObserver } from "@web/model/relational_model/utils";
import {
    referenceField,
    referenceFieldProps,
    ReferenceField,
} from "@web/views/fields/reference/reference_field";

export const pbxForwardDestinationRefFieldProps = {
    ...referenceFieldProps,
    kindField: t.string(),
};

export class PbxForwardDestinationRefField extends ReferenceField {
    props = useProps(pbxForwardDestinationRefFieldProps);

    setup() {
        super.setup();
        useRecordObserver((record) => {
            const kind = record.data[this.props.kindField];
            const destination = record.data[this.props.name];
            if (destination && destination.resModel !== kind) {
                record.update({ [this.props.name]: false });
            }
        });
    }

    get hideModelSelector() {
        return true;
    }

    getRelation() {
        const kind = this.props.record.data[this.props.kindField];
        return kind && kind !== "external" ? kind : undefined;
    }

    updateM2O(value) {
        // The inherited method prefers its cached relation, which may still refer to the
        // previous kind after switching models. The kind field is authoritative here.
        this.props.record.update({
            [this.props.name]: value && {
                resModel: this.getRelation(),
                resId: value.id,
                displayName: value.display_name,
            },
        });
    }
}

export const pbxForwardDestinationRefField = {
    ...referenceField,
    component: PbxForwardDestinationRefField,
    displayName: _t("PBX Forward Destination"),
    extractProps(staticInfo, dynamicInfo) {
        const props = referenceField.extractProps(staticInfo, dynamicInfo);
        props.kindField = staticInfo.options.kind_field;
        return props;
    },
};

registry.category("fields").add("voip_pbx_forward_destination_ref", pbxForwardDestinationRefField);
