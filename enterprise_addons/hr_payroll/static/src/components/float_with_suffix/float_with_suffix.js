import { registry } from "@web/core/registry";
import { 
    FloatWithoutTrailingZeros, 
    floatWithoutTrailingZeros 
} from "@hr/components/float_without_trailing_zeros/float_without_trailing_zeros";

class FloatWithSuffix extends FloatWithoutTrailingZeros {
    get formattedValue() {
        let value = super.formattedValue;

        const suffix = this.props.record.data.input_suffix;
        if (suffix) {
            value += ` ${suffix}`;
        }
        return value;
    }
}

export const floatWithSuffix = {
    ...floatWithoutTrailingZeros,
    component: FloatWithSuffix,
    fieldDependencies: [
        ...(floatWithoutTrailingZeros.fieldDependencies || []),
        { name: "input_suffix", type: "char" },
    ],
};

registry.category("fields").add("float_with_suffix", floatWithSuffix);
