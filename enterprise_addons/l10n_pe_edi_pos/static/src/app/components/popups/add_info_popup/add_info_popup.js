import { Component, proxy, t, useProps } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { Dialog } from "@web/core/dialog/dialog";

export class AddInfoPopup extends Component {
    static template = "l10n_pe_edi_pos.AddInfoPopup";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        getPayload: t.function(),
        order: t.instanceOf(PosOrder),
    });

    setup() {
        this.pos = usePos();
        this.state = proxy({
            l10n_pe_edi_refund_reason: this.props.order.l10n_pe_edi_refund_reason || "01",
        });
    }

    async confirm() {
        this.props.getPayload(this.state);
        this.props.close();
    }
}
