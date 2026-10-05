import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";

patch(PartnerList.prototype, {
    setup() {
        super.setup(...arguments);
    },

    //@override
    clickPartner(partner) {
        if (this.pos.company.country_id?.code !== "MX") {
            super.clickPartner(partner);
            return;
        }
        const order = this.pos.getOrder();
        if (order.isToInvoice() && !order.l10n_mx_edi_cfdi_to_public) {
            if (!partner) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("CFDI to Public"),
                    body: _t(
                        "Cannot remove the selected partner if an invoice is requested and not set to public."
                    ),
                });
                return;
            } else if (!(partner.zip && partner.country_code)) {
                this.pos.dialog.add(AlertDialog, {
                    title: _t("CFDI to Public"),
                    body: _t(
                        "Cannot select a partner with no country and ZIP code if the invoice is not set to public."
                    ),
                });
                return;
            }
        }
        super.clickPartner(partner);
    },
});
