import { Component, useProps, t } from "@odoo/owl";
import { Header, Body, Footer } from "@l10n_it_pos/app/documents/fiscal_document";
import { PrintRecMessage } from "@l10n_it_pos/app/fiscal_printer/commands";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export class FiscalInvoice extends Component {
    static template = "l10n_it_pos.FiscalInvoice";

    static components = {
        Header,
        PrintRecMessage,
        Body,
        Footer,
    };

    props = useProps({
        order: t.instanceOf(PosOrder),
    });

    setup() {
        this.order = this.props.order;
    }

    get client() {
        return this.order.getPartnerName();
    }
}
