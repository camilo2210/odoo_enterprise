import { Component, useProps, t, signal } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary, formatPercentage } from "@web/views/fields/formatters";
import { useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { usePopover } from "@web/core/popover/popover_hook";
import { BankRecFormDialog } from "../bankrec_form_dialog/bankrec_form_dialog";
import { BankRecLineInfoPopOver } from "../line_info_pop_over/line_info_pop_over";
import { x2ManyCommands } from "@web/core/orm_plugin";
import { roundDecimals } from "@web/core/utils/numbers";
import { BadgeTag } from "@web/core/tags_list/badge_tag";

export class BankRecLineToReconcile extends Component {
    static template = "account_accountant.BankRecLineToReconcile";

    static components = {
        BadgeTag,
    };

    props = useProps({
        line: t.object(),
        statementLine: t.object(),
    });

    lineInfoRef = signal.ref();

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this.ui = useService("ui");
        this.bankReconciliation = useBankReconciliation();

        this.lineInfoPopOver = usePopover(BankRecLineInfoPopOver, {
            position: "left",
            closeOnClickAway: true,
        });
    }

    onClickLine() {
        if (this.ui.isSmall) {
            this.toggleEditLine();
        }
    }

    /**
     * Opens a dialog to edit a bank statement line and saves any changes.
     *
     * This method:
     * - Opens a dialog (`FormViewDialog`) to allow the user to edit the current `account.move.line`.
     * - On saving, the dialog triggers the `onRecordSave` callback, which:
     *   - Calls `edit_bank_statement_line` on the ORM to update the bank statement line.
     *   - Reloads the statement line data.
     *   - Updates the chatter on the related journal entry.
     */
    toggleEditLine() {
        this.dialogService.add(BankRecFormDialog, {
            title: _t("Edit Line"),
            resModel: "account.move.line",
            resId: this.lineData.id,
            context: {
                skip_analytic_sync: true,
                form_view_ref: "account_accountant.view_bank_rec_edit_line",
                is_reviewed: ["reviewed", "supervised"].includes(
                    this.lineData.move_id.review_state
                ),
            },
            onRecordSave: async (record) => {
                const changes = await record.getChanges();
                await this.orm.call("account.bank.statement.line", "edit_reconcile_line", [
                    this.statementLineData.id,
                    this.lineData.id,
                    changes,
                ]);
                if (Object.keys(changes?.analytic_distribution || {}).length) {
                    await this.bankReconciliation.checkAnalyticAccounts(
                        changes?.analytic_distribution
                    );
                }
                this.props.statementLine.load();
                this.bankReconciliation.reloadChatter();
                return true;
            },
        });
    }

    /**
     * Deletes a line to reconcile.
     *
     * This method:
     * - Calls `delete_reconciled_line` on the ORM to delete the line.
     * - Reloads the statement line data after deletion.
     * - Updates the chatter on the related journal entry.
     */
    async deleteLine() {
        await this.orm.call("account.bank.statement.line", "delete_reconciled_line", [
            this.statementLineData.id,
            this.lineData.id,
        ]);
        if (this.lineData.first_reconciled_lines_id) {
            // Only update the line count per partner if we delete
            // a line which is reconciled to another move line
            // We don't use await here as it could be reloaded asynchronously.
            this.bankReconciliation.computeReconcileLineCountPerPartnerId(
                this.env.model.root.records
            );
        }
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    get jsonToData() {
        const jsonFieldValue = this.lineData.analytic_distribution;
        const analyticAccountIds = jsonFieldValue
            ? Object.keys(jsonFieldValue)
                  .filter((key) => key !== "__update__")
                  .map((key) => key.split(","))
                  .flat()
                  .map((id) => parseInt(id))
            : [];

        const fetchedAnalyticAccounts = new Map(
            analyticAccountIds.map((id) => [
                id,
                this.bankReconciliation.availableAnalyticAccounts?.[id],
            ])
        );
        return this.buildDistribution(jsonFieldValue, fetchedAnalyticAccounts);
    }

    buildDistribution(jsonFieldValue, analyticAccount) {
        const distribution = [];
        let id = 1;
        for (const [accountIds, percentage] of Object.entries(jsonFieldValue)) {
            if (accountIds === "__update__") {
                continue;
            }
            const defaultVals = []; // empty if the popup was not opened
            const ids = accountIds.split(",");

            for (const id of ids) {
                const account = analyticAccount.get(parseInt(id));
                if (!account) {
                    continue;
                }
                // since tags are displayed even though plans might not be retrieved (ie defaultVals is empty)
                // push the accounts anyway, as order doesn't matter
                // once the popup is opened, plans are fetched and the analyticAccounts list will be ordered
                Object.assign(
                    defaultVals.find((plan) => plan.planId === account.root_plan_id[0]) ||
                        (defaultVals.push({}) && defaultVals[defaultVals.length - 1]),
                    {
                        accountId: parseInt(id),
                        accountDisplayName: account.display_name,
                        accountColor: account.color,
                        accountRootPlanId: account.root_plan_id[0],
                    }
                );
            }
            distribution.push({
                analyticAccounts: defaultVals,
                percentage: percentage / 100,
                id: id++,
            });
        }
        return distribution;
    }

    planIsComplete(total) {
        return roundDecimals(total, 2) === 1;
    }

    /**
     * Computes the totals for each account, grouped by plan (primarily used in tags)
     * @returns {Object}
     */
    accountTotalsByPlan() {
        const accountTotals = {};
        this.jsonToData.map((line) => {
            line.analyticAccounts.map((column) => {
                if (column.accountId) {
                    let {
                        accId = column.accountId,
                        accName = column.accountDisplayName,
                        total = 0.0,
                        planId = column.accountRootPlanId,
                        planColor = column.accountColor,
                    } = accountTotals[column.accountRootPlanId]?.[column.accountId] || {};

                    total += roundDecimals(line.percentage, 2);

                    accountTotals[planId] = accountTotals[planId] || {};
                    accountTotals[planId][accId] = { accId, accName, planId, total, planColor };
                }
            });
        });
        return accountTotals;
    }

    planSummaryTags() {
        const accountTotals = this.accountTotalsByPlan();
        return Object.values(accountTotals).map((planSummary) => {
            const accs = Object.values(planSummary);
            return {
                id: accs[0].planId,
                text: accs.reduce(
                    (p, n) =>
                        p +
                        (p.length ? " | " : "") +
                        (this.planIsComplete(n.total)
                            ? n.accName
                            : `${formatPercentage(n.total)} ${n.accName}`),
                    ""
                ),
                color: accs[0].planColor,
            };
        });
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------
    openMove() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: this.moveData.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openPartner() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.lineData.partner_id.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    hoverLineInfoPopOver() {
        const popoverConfig = {
            statementLineData: this.statementLineData,
            lineData: this.lineData,
            isPartiallyReconciled: this.isPartiallyReconciled,
        };
        if (this.exchangeMove) {
            popoverConfig.exchangeMove = this.exchangeMove;
        }
        if (!this.lineInfoPopOver.isOpen && this.showLineInfo) {
            this.lineInfoPopOver.open(this.lineInfoRef(), popoverConfig);
        }
    }

    async deleteTax(taxIndex) {
        const taxChanged = this.lineDataTaxIds[taxIndex];
        await this.orm.call("account.bank.statement.line", "edit_reconcile_line", [
            this.statementLineData.id,
            this.lineData.id,
            { tax_ids: [[x2ManyCommands.UNLINK, taxChanged.data.id]] },
        ]);
        this.props.statementLine.load();
        this.bankReconciliation.reloadChatter();
    }

    // -----------------------------------------------------------------------------
    // GETTER
    // -----------------------------------------------------------------------------
    get statementLineData() {
        return this.props.statementLine.data;
    }

    get lineData() {
        return this.props.line;
    }

    get reconciledLineId() {
        return this.lineData.count_reconciled_lines === 1
            ? this.lineData.first_reconciled_lines_id
            : null;
    }

    get reconciledLineExcludingExchangeDiffId() {
        return this.lineData.count_reconciled_lines_excluding_exchange_diff === 1
            ? this.lineData.first_reconciled_lines_excluding_exchange_diff_id
            : null;
    }

    get moveData() {
        return (
            this.reconciledLineId?.move_id ||
            this.reconciledLineExcludingExchangeDiffId?.move_id ||
            this.lineData.move_id
        );
    }

    get isPartiallyReconciled() {
        if (!this.reconciledLineId) {
            return false;
        }
        return !this.reconciledLineId.full_reconcile_id?.id;
    }

    get hasDifferentCurrencies() {
        return this.lineData.currency_id.id !== this.statementLineData.currency_id.id;
    }

    get formattedAmountCurrencyOfLine() {
        return formatMonetary(this.lineData.amount_currency, {
            currencyId: this.lineData.currency_id.id,
        });
    }

    get formattedAmountCurrencyOfStatementLine() {
        return formatMonetary(this.lineData.amount_currency, {
            currencyId: this.statementLineData.currency_id.id,
        });
    }

    get exchangeMove() {
        return this.lineData.exchange_move_ids.records.length === 1
            ? this.lineData.exchange_move_ids.records[0].data
            : null;
    }

    get showLineInfo() {
        return this.isPartiallyReconciled || this.exchangeMove?.id;
    }

    get isTaxLine() {
        return this.lineData.tax_line_id && !this.lineData.account_id.reconcile;
    }

    get lineDataTaxIds() {
        return this.lineData.tax_ids.records;
    }
}
