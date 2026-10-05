import { BankRecButtonList } from "../button_list/button_list";
import { BankRecLineToReconcile } from "../line_to_reconcile/line_to_reconcile";
import { BankRecReconciledLineName } from "../reconciled_line_name/reconciled_line_name";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatMonetary } from "@web/views/fields/formatters";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, signal, computed } from "@odoo/owl";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { floatIsZero } from "@web/core/utils/numbers";

export class BankRecStatementLine extends KanbanRecord {
    static template = "account_accountant.BankRecStatementLine";
    static components = {
        BankRecLineToReconcile,
        BankRecButtonList,
        DropdownItem,
        BankRecReconciledLineName,
    };

    allLinesInSameForeignCurrency = computed(() => this._computeAllLinesInSameForeignCurrency());
    accountMoveLines = computed(() => this.recordData.line_ids.records.map((line) => line.data));
    hasAttachment = computed(() => this._computeHasAttachment());
    hasInvalidAnalytics = computed(() =>
        this.linesToReconcile().some((line) => line.has_invalid_analytics)
    );
    isUnfolded = signal(false);
    linesToReconcile = computed(() => this._computeLinesToReconcile());
    suspenseAccountLine = computed(() => {
        const suspenseId = this.recordData.journal_id?.suspense_account_id.id;
        return this.accountMoveLines().find((line) => line.account_id.id === suspenseId);
    });

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.bankReconciliation = useBankReconciliation();
        if (this.env.model.config.context?.default_st_line_id === this.props.record.resId) {
            this.isUnfolded.set(true);
            this.bankReconciliation.selectStatementLine(this.props.record);
        }
        onWillStart(async () => {
            this.userCanReview = await user.hasGroup("account.group_account_user");
        });
    }

    getCardClasses() {
        let classes = super.getCardClasses();
        classes += " mb-0";
        if (this.numberOfStatementLines === 1) {
            classes += " mt-3";
        }
        return classes;
    }

    // -----------------------------------------------------------------------------
    // ACTION
    // -----------------------------------------------------------------------------

    openStatementCreate() {
        this.action.doAction("account_accountant.action_bank_statement_form_bank_rec_widget", {
            additionalContext: {
                split_line_id: this.recordData.id,
                default_journal_id: this.recordData.journal_id.id,
            },
            onClose: async () => {
                this.env.model.load();
            },
        });
    }

    openPartner() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.partner.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async removePartner() {
        await this.orm.write("account.bank.statement.line", [this.recordData.id], {
            partner_id: false,
        });
        this.record.load();
    }

    async undoReconciliation() {
        await this.orm.call(
            "account.bank.statement.line",
            "action_undo_reconciliation",
            [this.recordData.id],
            {
                context: {
                    skip_account_move_synchronization: true,
                },
            }
        );
        this.record.load();
    }

    // -----------------------------------------------------------------------------
    // HELPER
    // -----------------------------------------------------------------------------

    _computeLinesToReconcile() {
        const suspenseId = this.recordData.journal_id?.suspense_account_id.id;
        const defaultId = this.recordData.journal_id?.default_account_id.id;
        return this.accountMoveLines().filter(
            (line) => line.account_id.id !== suspenseId && line.account_id.id !== defaultId
        );
    }

    _computeAllLinesInSameForeignCurrency() {
        return (
            this.recordData.foreign_currency_id &&
            this.linesToReconcile().length > 0 &&
            this.linesToReconcile().every(
                (line) => line.currency_id.id === this.recordData.foreign_currency_id.id
            )
        );
    }

    /**
     * Checks if there is at least one attachment associated with the bank statement line or its related records.
     *
     * This getter aggregates attachment counts from attachment_ids field which is a compute for:
     * - The bank statement line record itself or the related move since attachment_ids is a related to move_id.attachment_ids.
     * - The related move lines themselves, if they have attachments directly associated (`line.move_attachment_ids`)
     *   except the attachments link to the statement.
     * - The lines reconciled with the related move lines, specifically checking for attachments on the
     *   move associated with those reconciled lines.
     *
     * This check ensures that all attachments from associated invoices, bills, and other related documents are considered.
     *
     * @returns {number} The total number of attachments found. A return value greater than 0 indicates the presence of attachments.
     */
    _computeHasAttachment() {
        return this.recordData.has_attachments;
    }

    get record() {
        return this.props.record;
    }

    get recordData() {
        return this.props.record.data;
    }

    toggleUnfold(event) {
        if (event?.pointerType === "mouse") {
            this.isUnfolded.set(!this.isUnfolded());
        }
        this.selectStatementLine(event);
    }

    selectStatementLine(event) {
        // In case we are on a mobile device, we want to keep the old onClick behaviour
        if (this.recordData.is_reconciled && event?.pointerType !== "mouse") {
            this.isUnfolded.set(!this.isUnfolded());
        }
        // Update the chatter with the last selected element
        this.bankReconciliation.selectStatementLine(this.record);
    }

    openChatter() {
        this.bankReconciliation.selectStatementLine(this.record);
        this.bankReconciliation.openChatter();
    }

    get numberOfStatementLines() {
        return this.env.model.root.count;
    }

    get formattedAmount() {
        return formatMonetary(this.recordData.amount, {
            currencyId: this.recordData.currency_id.id,
        });
    }

    get formattedDate() {
        return this.recordData.date.toLocaleString({
            month: "short",
            day: "2-digit",
        });
    }

    get formattedFullDate() {
        return this.recordData.date.toLocaleString({
            month: "long",
            day: "numeric",
            year: "numeric",
        });
    }

    get partner() {
        return this.recordData.partner_id;
    }

    get suspenseAccountLineFormattedAmount() {
        return formatMonetary(this.suspenseAccountLine().amount_currency, {
            currencyId: this.suspenseAccountLine()?.currency_id.id,
        });
    }

    get activityNumber() {
        return this.recordData.activity_ids.count;
    }

    get amountClasses() {
        const { foreign_currency_id: foreignCurrencyId, amount } = this.recordData;
        const classes = foreignCurrencyId ? "w-50" : "w-100";
        if (this.isDraft && !floatIsZero(amount)) {
            return `${classes} text-info`;
        }

        if (amount > 0) {
            return `${classes} fw-bold`;
        }
        if (amount < 0) {
            return `${classes} text-danger fw-bold`;
        }
        return `${classes} text-secondary`;
    }

    get buttonListProps() {
        return {
            statementLineRootRef: this.rootRef,
            statementLine: this.record,
            reconcileLineCount:
                this.bankReconciliation.reconcileCountPerPartnerId[this.recordData.partner_id.id] ??
                null,
            reconcileModels:
                this.bankReconciliation.reconcileModelPerStatementLineId[this.recordData.id] ?? [],
            preSelectedReconciliationModel: this.accountMoveLines()
                .filter(
                    (line) =>
                        line.reconcile_model_id.id &&
                        // We don't want to show the button for matching rules as they are only automatic.
                        line.reconcile_model_id.rule_type === "reco_model"
                )
                .map((line) => line.reconcile_model_id)?.[0],
        };
    }

    get formattedAmountCurrencyInForeign() {
        return formatMonetary(this.recordData.amount_currency, {
            currencyId: this.recordData.foreign_currency_id.id,
        });
    }

    get isSelected() {
        return this.recordData.id === this.bankReconciliation.statementLineId;
    }

    get isChatterOpen() {
        return this.bankReconciliation.chatterState.visible;
    }

    get isDraft() {
        return this.recordData.state === "draft";
    }
}
