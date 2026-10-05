import { Component, useProps, t } from "@odoo/owl";
import { PrintRecMessage } from "@l10n_it_pos/app/fiscal_printer/commands";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export class Header extends Component {
    static template = "l10n_it_pos.FiscalDocumentHeader";

    static components = {
        PrintRecMessage,
    };

    props = useProps({
        order: t.instanceOf(PosOrder),
    });

    setup() {
        this.order = this.props.order;
    }
}
