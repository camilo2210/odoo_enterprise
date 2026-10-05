import { SoLineCreateButton } from "@sale_service/components/so_line_create_button/so_line_create_button";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { computeM2OProps } from "@web/views/fields/many2one/many2one";
import { buildM2OFieldDescription } from "@web/views/fields/many2one/many2one_field";

export class SlotSaleLineIdMany2OneField extends SoLineCreateButton {
    get m2oProps() {
        const props = computeM2OProps(this.props);
        const { record } = this.props;
        if (record.data.allow_billable && !record.data.under_warranty) {
            props.placeholder = _t("Billable");
        }
        return props;
    }
}

registry.category("fields").add("slot_sale_line_id", {
    ...buildM2OFieldDescription(SlotSaleLineIdMany2OneField),
    fieldDependencies: [
        { name: "allow_billable", type: "boolean" },
        { name: "under_warranty", type: "boolean" },
    ]
});
