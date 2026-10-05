import { proxy } from "@odoo/owl";
import { BankReconciliationService } from "@account_accountant/components/bank_reconciliation/bank_reconciliation_service";
import { patch } from "@web/core/utils/patch";

patch(BankReconciliationService.prototype, {
    setup(env, services) {
        super.setup(...arguments);
        this.partnersWithSales = proxy({});
    },
    async fetchPartnersWithSales(records) {
        const partnerIds = records
            .filter((record) => !!record.data.partner_id.id)
            .map((record) => record.data.partner_id.id);

        const groups = await this.orm.formattedReadGroup(
            "sale.order",
            [
                ["partner_id", "in", partnerIds],
                ["invoice_status", "!=", "invoiced"],
            ],
            ["partner_id"],
            ["amount_total:array_agg"]
        );
        this.partnersWithSales = {};
        groups.forEach((group) => {
            this.partnersWithSales[group.partner_id[0]] = group["amount_total:array_agg"];
        });
    },
    async updatePartnersWithSales(partnerId) {
        if (partnerId in this.partnersWithSales) {
            return;
        }
        const result = await this.orm.webSearchRead(
            "sale.order",
            [
                ["partner_id", "=", partnerId],
                ["invoice_status", "!=", "invoiced"],
            ],
            {
                specification: {
                    amount_total: {},
                },
            }
        );

        this.partnersWithSales[partnerId] = result.records.map(
            (saleOrder) => saleOrder.amount_total
        );
    },
});
