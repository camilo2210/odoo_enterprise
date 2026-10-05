import { Component, useProps, t } from "@odoo/owl";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export class PrintContentByNumbers extends Component {
    static template = "l10n_it_pos.PrintContentByNumbers";
    props = useProps({
        order: t.instanceOf(PosOrder),
    });

    setup() {
        this.receiptNumber = this.props.order.it_fiscal_receipt_number;
        if (!this.props.order.it_fiscal_receipt_date) {
            return;
        }

        const dateParts = this.props.order.it_fiscal_receipt_date.split("/");
        this.day = dateParts[0];
        this.month = dateParts[1];
        this.year = dateParts[2];
    }
}
