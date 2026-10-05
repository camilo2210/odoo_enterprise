import { PartnerLine } from "@point_of_sale/app/screens/partner_list/partner_line/partner_line";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { CustomSelectCreateDialog } from "@pos_settle_due/app/views/view_dialogs/select_create_dialog";
import { useService } from "@web/core/utils/hooks";

patch(PartnerLine.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
        this.dialog = useService("dialog");
    },
    get limitReached() {
        return (
            this.props.partner.over_due &&
            this.props.isSelected &&
            this.props.partner.creditLimit > 0
        );
    },
    get totalDue() {
        return this.props.partner.commercial_partner_id?.total_due || 0;
    },
    onClickDepositMoney(amount = 0) {
        const partnerId = this.props.partner.id;
        const commercialPartnerId = this.props.partner.raw.commercial_partner_id;
        const success = this.pos.onClickDepositMoney(amount, partnerId, commercialPartnerId);
        if (!success) {
            this.props.close();
            return;
        }
        this.props.onClickPartner(this.props.partner);
    },
    payLaterPaymentExists() {
        return this.pos.models["pos.payment.method"].some(
            (pm) =>
                this.pos.config.payment_method_ids.some((m) => m.id === pm.id) &&
                pm.type === "pay_later"
        );
    },
    async settleCustomerInvoices() {
        this.props.close();
        const partnerId = this.props.partner.id;
        const commercialPartnerId = this.props.partner.raw.commercial_partner_id;
        this.dialog.add(CustomSelectCreateDialog, {
            resModel: "account.move",
            noCreate: true,
            multiSelect: true,
            listViewId: this.pos.config._pos_settle_due_due_account_move_list_view_id,
            domain: [
                ["commercial_partner_id", "=", commercialPartnerId],
                ["amount_residual", "!=", 0],
                ["move_type", "in", ["out_invoice", "out_receipt", "out_refund"]],
                ["payment_state", "in", ["not_paid", "partial"]],
            ],
            onSelected: async (invoiceIds) => {
                this.pos.onClickSettleInvoices(invoiceIds, partnerId, commercialPartnerId);
            },
        });
    },
});
