import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { BankRecQuickCreate } from "./quick_create/quick_create";
import { BankRecKanbanController } from "./kanban_controller";
import { BankRecStatementLine } from "./statement_line/statement_line";
import { BankRecStatementSummary } from "./statement_summary/statement_summary";
import { browser } from "@web/core/browser/browser";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { onWillStart, onWillDestroy, proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "./bank_reconciliation_service";
import { BankRecControlPanel } from "./control_action/control_action";
import { user } from "@web/core/user";

export class BankRecKanbanRenderer extends KanbanRenderer {
    static template = "account_accountant.BankRecKanbanRenderer";
    static components = {
        ...KanbanRenderer.components,
        BankRecQuickCreate,
        BankRecStatementSummary,
        BankRecStatementLine,
        Chatter,
    };

    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.bankReconciliation = useBankReconciliation();
        this.globalState = proxy({
            resModel: this.env.model.config.resModel,
            context: this.env.model.config.context,
            journalId:
                this.env.model.config.context.default_journal_id ||
                this.env.model.config.context.active_id,
            totalJournalAmount: "",
        });

        this.env.model.hooks.onRootLoaded = async (newRoot) => {
            await this.prepareInitialState(newRoot.records);
        };

        onWillStart(async () => {
            await this.prepareInitialState(this.env.model.root.records);
        });

        onWillDestroy(() => {
            browser.sessionStorage.setItem(
                "isBankReconciliationWidgetChatterOpened",
                this.bankReconciliation.chatterState.visible
            );
            browser.sessionStorage.setItem(
                "bankReconciliationStatementLineId",
                this.bankReconciliation.statementLineId
            );
            this.bankReconciliation.chatterState.statementLine = null;
        });
    }

    /**
     * Prepare the initial bank reconciliation widget info on load or when records changes
     *
     * @param {Array<Object>} records - Bank statement line records
     * @returns {Promise<void>} Resolves when all computations are done
     */
    async prepareInitialState(records) {
        this.bankReconciliation.modelRootRecords = records;
        await Promise.all([
            this.getJournalTotalAmount(),
            this.bankReconciliation.computeReconcileLineCountPerPartnerId(records),
            this.bankReconciliation.computeAvailableReconcileModels(records),
            this.bankReconciliation.computeAvailableReconcileLines(records),
            this.bankReconciliation.computeAvailableAnalyticAccounts(records),
        ]);
        const statementLineId =
            parseInt(browser.sessionStorage.getItem("bankReconciliationStatementLineId")) ||
            records[0]?.data.id;
        const statementLine =
            records.find((record) => record.data.id === statementLineId) ?? records[0];
        this.bankReconciliation.selectStatementLine(statementLine);
    }

    /**
        Override.
    **/
    async validateQuickCreate(recordId) {
        // When adding a record, some information needs to be recomputed
        await this.bankReconciliation.updateAvailableReconcileModels(recordId);
        await this.env.model.load();
        await this.getJournalTotalAmount();
        await this.bankReconciliation.computeReconcileLineCountPerPartnerId(
            this.env.model.root.records
        );
    }

    async getJournalTotalAmount() {
        const value = await this.orm.call("account.journal", "get_total_journal_amount", [
            this.globalState.journalId,
        ]);
        this.globalState.totalJournalAmount = value.balance_amount;
        this.globalState.totalIsInvalid = value.has_invalid_statements;
        return value;
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------
    async actionOpenBankGL() {
        const actionData = await this.orm.call(
            "account.journal",
            "action_open_bank_balance_in_gl",
            [
                this.env.model.config.context.default_journal_id ||
                    this.env.model.config.context.active_id,
            ]
        );
        this.action.doAction(actionData);
    }

    actionOpenStatement(statementId) {
        const action = {
            type: "ir.actions.act_window",
            res_model: "account.bank.statement",
            res_id: statementId,
            views: [[false, "form"]],
            target: "current",
            context: {
                form_view_ref: "account_accountant.view_bank_statement_form_bank_rec_widget",
                from_bank_reco: false,
                from_statement_view: true,
                default_journal_id: this.globalState.journalId,
            },
        };

        this.action.doAction(action);
    }

    async actionReviewStatement(statementId) {
        const action = await this.orm.call(
            "account.bank.statement",
            "action_open_statements_to_review",
            [statementId],
            { context: this.globalState.context }
        );
        this.action.doAction(action);
    }

    // -----------------------------------------------------------------------------
    // GETTER
    // -----------------------------------------------------------------------------

    get quickCreateContext() {
        // This is needed because you could end up with inconsistent between the model context
        // and the user context, since the kanban controller directly modifies the user context,
        // we put priority on the user context.
        return {
            ...this.globalState.context,
            ...user.context,
        };
    }

    get numberOfStatementLines() {
        return this.env.model.root.count;
    }

    get totalJournalLabel() {
        return _t("Current Balance");
    }

    // hide no content helper if quick create is visible and there is no data either isGrouped or not
    get showNoContentHelper() {
        return !this.props.quickCreateState?.isOpen && !this.props.list.model.hasData();
    }

    /**
    Prepares a list of statements based on the statement_id of the bank statement line records.
    Statements are only displayed above the first line of the statement (all lines might not be visible in the kanban)
    **/
    get statementGroups() {
        const statementGroups = {};
        let lastStatementId = null;
        for (const record of this.env.model.root.records) {
            const statementId = record.data.statement_id?.id;
            if (statementId && statementId !== lastStatementId) {
                // Add the statement group information to the statementGroups object
                statementGroups[record.data.id] = {
                    statementId: statementId,
                    name: record.data.statement_name,
                    balance: formatMonetary(record.data.statement_balance_end_real, {
                        currencyId: record.data.currency_id.id,
                    }),
                    isValid: record.data.statement_complete && record.data.statement_valid,
                    problemDescription: record.data.statement_problem_description,
                };
                lastStatementId = statementId;
            } else {
                if (
                    Object.keys(statementGroups).length &&
                    !statementId &&
                    typeof lastStatementId !== "string"
                ) {
                    statementGroups[record.data.id] = {
                        name: _t("No Bank Statement"),
                        isValid: true,
                    };
                    lastStatementId = "no_bank_statement";
                }
            }
        }
        return statementGroups;
    }

    get isReviewFilterActive() {
        const reviewFilter = Object.values(this.env.searchModel.searchItems).find(
            ({ name }) => name === "statement_to_review"
        );

        return this.env.searchModel.facets.some(
            (facet) =>
                facet.groupId === reviewFilter?.groupId &&
                facet.values.includes(reviewFilter.description)
        );
    }
}

export class BankRecModel extends RelationalModel {
    static withCache = false;
}

export const BankRecKanbanView = {
    ...kanbanView,
    ControlPanel: BankRecControlPanel,
    Controller: BankRecKanbanController,
    Renderer: BankRecKanbanRenderer,
    Model: BankRecModel,
    searchMenuTypes: ["filter", "favorite"],
};

registry.category("views").add("bank_rec_widget_kanban", BankRecKanbanView);
