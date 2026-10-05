import { EventBus, proxy } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Domain } from "@web/core/domain";

export class BankReconciliationService {
    constructor(env, services) {
        this.env = env;
        this.setup(env, services);
    }

    setup(env, services) {
        this.bus = new EventBus();
        this.orm = services["orm"];
        this.batchedOrm = services["batchedOrm"];

        this.chatterState = proxy({
            visible:
                JSON.parse(
                    browser.sessionStorage.getItem("isBankReconciliationWidgetChatterOpened")
                ) ?? false,
            statementLine: null,
        });
        this.reconcileCountPerPartnerId = proxy({});
        this.reconcileModelPerStatementLineId = proxy({});
        this.availableReconcileLines = proxy({});
        this.availableAnalyticAccounts = proxy({});
        this.modelRootRecords = null;
    }

    toggleChatter() {
        this.chatterState.visible = !this.chatterState.visible;
        browser.sessionStorage.setItem(
            "isBankReconciliationWidgetChatterOpened",
            this.chatterState.visible
        );
    }

    /**
     * Specific function to open the chatter.
     * For a particular case, where the customer clicks on
     * the chatter icon directly on the bank statement line,
     * we want to open the chatter but not close it.
     */
    openChatter() {
        this.chatterState.visible = true;
    }

    selectStatementLine(statementLine) {
        this.chatterState.statementLine = statementLine;
    }

    reloadChatter() {
        this.bus.trigger("MAIL:RELOAD-THREAD", {
            model: "account.bank.statement.line",
            id: this.statementLineId,
        });
    }

    async computeAvailableReconcileLines(records) {
        this.availableReconcileLines = await this.orm.searchRead(
            "account.move.line",
            this.getAvailableReconciledLinesDomain(records),
            ["id", "amount_currency", "date"],
            { limit: 100, order: "date desc" }
        );
    }

    getAvailableReconciledLinesDomain(records) {
        return [
            ["parent_state", "in", ["draft", "posted"]],
            ["company_id", "child_of", records.map((record) => record.data.company_id.id)],
            ["search_account_id.reconcile", "=", true],
            ["display_type", "not in", ["line_section", "line_note"]],
            ["reconciled", "=", false],
            "|",
            ["search_account_id.account_type", "not in", ["asset_receivable", "liability_payable"]],
            ["payment_id", "=", false],
            ["statement_line_id", "not in", records.map((record) => record.resId)],
        ];
    }

    async computeReconcileLineCountPerPartnerId(records) {
        const domain = this.getAvailableReconciledLinesDomain(records);
        const partnerIds = records
            .filter((record) => !!record.data.partner_id?.id)
            .map((record) => record.data.partner_id.id);
        const finalDomain = Domain.and([[["partner_id", "in", partnerIds]], domain]).toList();
        const groups = await this.orm.formattedReadGroup(
            "account.move.line",
            finalDomain,
            ["partner_id"],
            ["id:count"]
        );

        this.reconcileCountPerPartnerId = {};
        groups.forEach((group) => {
            this.reconcileCountPerPartnerId[group.partner_id[0]] = group["id:count"];
        });
    }

    async computeAvailableReconcileModels(records) {
        this.reconcileModelPerStatementLineId =
            Object.keys(records).length === 0
                ? {}
                : await this.orm.call(
                      "account.reconcile.model",
                      "get_available_reconcile_model_per_statement_line",
                      [records.map((record) => record.resId)]
                  );
    }

    async updateAvailableReconcileModels(recordId) {
        const result = await this.orm.call(
            "account.reconcile.model",
            "get_available_reconcile_model_per_statement_line",
            [[recordId]]
        );
        this.reconcileModelPerStatementLineId[recordId] = result[recordId];
    }

    async checkAnalyticAccounts(analyticAccounts) {
        const analyticAccountIds = analyticAccounts
            ? Object.keys(analyticAccounts)
                  .filter((key) => key != "__update__")
                  .map((key) => key.split(","))
                  .flat()
                  .map((id) => parseInt(id))
            : [];

        const missingIds = analyticAccountIds.filter((id) => !this.availableAnalyticAccounts[id]);
        if (missingIds.length > 0) {
            const newlyFetchedAccounts = await this.fetchAnalyticAccounts([
                ["id", "in", missingIds],
            ]);
            this.availableAnalyticAccounts = {
                ...this.availableAnalyticAccounts,
                ...newlyFetchedAccounts,
            };
        }
    }

    async computeAvailableAnalyticAccounts(records) {
        const allDistributions = records
            .flatMap((record) => record.data.line_ids.records)
            .filter((line) => line.data.analytic_distribution)
            .map((line) => line.data.analytic_distribution);

        const analyticAccountIds = [
            ...new Set(
                allDistributions.flatMap((dist) =>
                    Object.keys(dist)
                        .filter((key) => key !== "__update__")
                        .flatMap((key) => key.split(","))
                        .map((id) => parseInt(id))
                )
            ),
        ];
        this.availableAnalyticAccounts = analyticAccountIds.length
            ? await this.fetchAnalyticAccounts([["id", "in", analyticAccountIds]])
            : [];
    }

    async fetchAnalyticAccounts(domain) {
        const args = {
            domain: domain,
            fields: ["id", "display_name", "root_plan_id", "color"],
            context: [],
        };
        // batched call
        const records = await this.batchedOrm.read(
            "account.analytic.account",
            domain[0][2],
            args.fields,
            {}
        );

        return Object.assign(
            {},
            ...records.map((r) => {
                const { id, ...rest } = r;
                return { [id]: rest };
            })
        );
    }

    async reloadRecords(records) {
        if (!records.length) {
            return;
        }
        const { model, config } = records[0];
        const resIds = records.map((r) => r.resId);
        const results = await model._loadRecords({ ...config, resId: null, resIds });
        for (const record of records) {
            const data = results.find((r) => r.id === record.resId);
            if (data) {
                record._setData(data);
            }
        }
    }

    async reloadRecordsByIds(ids) {
        if (!this.modelRootRecords || !ids.length) {
            return;
        }
        const records = this.modelRootRecords.filter((r) => ids.includes(r.resId));
        await this.reloadRecords(records);
    }

    get statementLineMove() {
        return this.chatterState.statementLine?.data.move_id;
    }

    get statementLineMoveId() {
        return this.statementLineMove?.id;
    }

    get statementLine() {
        return this.chatterState.statementLine;
    }

    get statementLineId() {
        return this.statementLine?.data?.id;
    }
}

const bankReconciliationService = {
    dependencies: ["orm", "batchedOrm"],
    start(env, services) {
        return new BankReconciliationService(env, services);
    },
};

registry.category("services").add("bankReconciliation", bankReconciliationService);

export function useBankReconciliation() {
    return proxy(useService("bankReconciliation"));
}
