import { registry } from "@web/core/registry";
import { BinaryField, binaryField } from "@web/views/fields/binary/binary_field";

export class BinaryFieldComission extends BinaryField {
    async update(changes) {
        const res = super.update(changes);
        if (changes.data) {
            await this.props.record.save();
        }
        return res;
    }
}

export const binaryFieldComission = {
    ...binaryField,
    component: BinaryFieldComission,
};

registry.category("fields").add('binary_commission', binaryFieldComission);
