import { BankReconciliationService } from "@account_accountant/components/bank_reconciliation/bank_reconciliation_service";
import { patch } from "@web/core/utils/patch";

patch(BankReconciliationService.prototype, {
    getAvailableReconciledLinesDomain(records) {
        // override the domain entirely to change the condition on the companies.
        // In the case of inter company transaction. For selected companies that have
        // the config for inter company we want to be able to select one of the move line
        // of other companies.
        const companyId = records.map((record) => record.data.company_id.id).at(-1);
        const availableInterCompanies = records.flatMap(
            (record) => record.data.available_inter_company_ids.records
        );
        const interCompanies = availableInterCompanies.filter(
            (company) => company.data.id !== companyId
        );
        if (!interCompanies.length) {
            return super.getAvailableReconciledLinesDomain(records);
        }

        const interCompanyIds = [...new Set(interCompanies.map((company) => company.data.id))];
        const excludedIntercoAccountIds = interCompanies.flatMap((company) => [
            company.data.account_interco_payable_id,
            company.data.account_interco_receivable_id,
        ]);

        return [
            ["parent_state", "in", ["draft", "posted"]],
            "|",
            ["company_id", "child_of", companyId],
            "&",
            ["company_id", "in", interCompanyIds],
            ["account_id", "not in", excludedIntercoAccountIds],
            ["search_account_id.reconcile", "=", true],
            ["display_type", "not in", ["line_section", "line_note"]],
            ["reconciled", "=", false],
            "|",
            ["search_account_id.account_type", "not in", ["asset_receivable", "liability_payable"]],
            ["payment_id", "=", false],
            ["statement_line_id", "not in", records.map((record) => record.resId)],
        ];
    },
});
