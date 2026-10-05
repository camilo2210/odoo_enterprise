import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { Component, proxy, useProps, t } from "@odoo/owl";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { ResPartner } from "@point_of_sale/app/models/res_partner";

export class AddInfoPopup extends Component {
    static template = "l10n_mx_edi_pos.AddInfoPopup";
    static components = { Dialog };
    props = useProps({
        order: t.instanceOf(PosOrder),
        getPayload: t.function(),
        close: t.function(),
        newPartner: t.instanceOf(ResPartner).optional(),
    });

    setup() {
        this.pos = usePos();
        const order = this.props.order;
        const partner = order.getPartner() || this.props.newPartner;
        // when opening the popup for the first time, both variables are undefined !
        this.state = proxy({
            l10n_mx_edi_usage: partner?.l10n_mx_edi_usage || order.l10n_mx_edi_usage || "G01",
            l10n_mx_edi_cfdi_to_public: !!order.l10n_mx_edi_cfdi_to_public,
        });
    }
    confirm() {
        const partner = this.props.order.getPartner() || this.props.newPartner;
        const isInvoicedToPublic =
            this.state.l10n_mx_edi_cfdi_to_public === true ||
            this.state.l10n_mx_edi_cfdi_to_public === "1";
        if ((!partner || !partner.zip || !partner.country_code) && !isInvoicedToPublic) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("CFDI to Public"),
                body: _t(
                    '"Invoice to public" cannot set to "No" if the selected partner does not have a recognized country and ZIP code set.'
                ),
            });
        } else {
            this.props.getPayload(this.state);
            this.props.close();
        }
    }
}
