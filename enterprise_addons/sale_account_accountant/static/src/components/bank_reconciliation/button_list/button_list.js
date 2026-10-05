import { t } from "@odoo/owl";
import {
    BankRecButtonList,
    bankRecButtonListProps,
} from "@account_accountant/components/bank_reconciliation/button_list/button_list";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";

Object.assign(bankRecButtonListProps, {
    hasSaleOrders: t.boolean().optional(),
    actionOpenSaleOrders: t.function().optional(),
});

patch(BankRecButtonList.prototype, {
    async _setPartnerOnReconcileLine(partnerId) {
        super._setPartnerOnReconcileLine(partnerId);
        await this.bankReconciliation.updatePartnersWithSales(partnerId);
    },

    get availableSaleOrder() {
        // No need to compute if the statement line has no partner
        if (!this.statementLineData.partner_id) {
            return [];
        }

        const statementLineAmount =
            this.statementLineData.amount_currency || this.statementLineData.amount;
        const decimalPlaces =
            this.statementLineData.foreign_currency_id?.decimal_places ||
            this.statementLineData.currency_id?.decimal_places;

        return this.bankReconciliation.partnersWithSales[
            this.statementLineData.partner_id.id
        ]?.filter((saleOrderAmount) =>
            floatIsZero(saleOrderAmount - statementLineAmount, decimalPlaces)
        );
    },

    get displaySuggestionPill() {
        return super.displaySuggestionPill || this.availableSaleOrder?.length;
    },

    get isSalesButtonShown() {
        return this.props.hasSaleOrders;
    },

    get buttons() {
        const buttonsToDisplay = super.buttons;
        if (this.isSalesButtonShown) {
            buttonsToDisplay.sale = {
                label: _t("Sales"),
                action: () => this.props.actionOpenSaleOrders(),
                classes: "sales-btn",
                suggestion: this.availableSaleOrder.length,
            };
        }
        return buttonsToDisplay;
    },
});
