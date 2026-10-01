import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useProps } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ChangeProductionQty extends Component {
    static template = "stock_barcode_mrp.ChangeProductionQty";

    props = useProps(standardFieldProps);

    setup() {
        this.actionService = useService("action");
    }

    async openChangeQtyWizard() {
        // Persist pending form edits (e.g. `qty_producing`) before opening the
        // wizard, otherwise the `onClose` reload would discard them.
        await this.props.record.save();
        this.actionService.doAction("mrp.action_change_production_qty", {
            additionalContext: {
                default_product_qty: this.props.value,
                default_mo_id: this.props.record.resId,
            },
            onClose: async () => await this.env.model.load(),
        });
    }
}

export const ChangeProductionQtyButton = {
    component: ChangeProductionQty,
};
registry.category("fields").add("change_production_qty", ChangeProductionQtyButton);
