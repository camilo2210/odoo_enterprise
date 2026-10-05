import { Dialog } from "@web/core/dialog/dialog";
import { Component, proxy, t, useProps } from "@odoo/owl";

export class ConfirmQuantDialog extends Component {
    static components = { Dialog };
    static template = "stock_barcode.ConfirmQuantDialog";

    props = useProps({
        close: t.function(),
        onConfirm: t.function(),
        onWaitReview: t.function(),
    });

    setup() {
        this.inventoryReason = proxy({ value: "Physical Inventory" });
    }

    onConfirm() {
        this.props.onConfirm({
            inventory_name: this.inventoryReason.value,
        });
        this.props.close();
    }

    onWaitReview() {
        this.props.onWaitReview();
        this.props.close();
    }

    onInventoryReasonChange(ev) {
        this.inventoryReason.value = ev.target.value;
    }
}
