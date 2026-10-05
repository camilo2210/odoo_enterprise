import { onWillDestroy } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { makeActiveField } from "@web/model/relational_model/utils";
import { useService } from "@web/core/utils/hooks";
import { useBankReconciliation } from "./bank_reconciliation_service";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { user } from "@web/core/user";

export class BankRecKanbanController extends KanbanController {
    static template = "account_accountant.BankRecoKanbanController";

    async setup() {
        super.setup();
        this.orm = useService("orm");
        this.bankReconciliation = useBankReconciliation();
        useHotkey("alt+shift+c", () => this.bankReconciliation.toggleChatter(), {
            bypassEditableProtection: true,
            withOverlay: () => this.rootRef().querySelector(".bank-chatter-btn"),
        });
        user.updateContext({ from_bank_reco: true, auto_statement_processing: true });
        onWillDestroy(() => {
            user.updateContext({ from_bank_reco: false, auto_statement_processing: false });
        });
    }

    async createRecord() {
        this.quickCreateState.openQuickCreate();
    }

    get modelParams() {
        const params = super.modelParams;
        params.config.activeFields.move_id = makeActiveField();
        params.config.activeFields.move_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                review_state: { name: "review_state", type: "char" },
                inalterable_hash: { name: "inalterable_hash", type: "char" },
            },
            activeFields: {
                review_state: makeActiveField(),
                inalterable_hash: makeActiveField(),
            },
        };
        params.config.activeFields.partner_id = makeActiveField();
        params.config.activeFields.statement_line_attachment_ids = makeActiveField();
        params.config.activeFields.partner_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                property_account_receivable_id: {
                    name: "property_account_receivable_id",
                    type: "many2one",
                },
                property_account_payable_id: {
                    name: "property_account_payable_id",
                    type: "many2one",
                },
                customer_rank: { name: "customer_rank", type: "int" },
                supplier_rank: { name: "supplier_rank", type: "int" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                property_account_receivable_id: makeActiveField(),
                property_account_payable_id: makeActiveField(),
                customer_rank: makeActiveField(),
                supplier_rank: makeActiveField(),
            },
        };
        params.config.activeFields.currency_id = makeActiveField();
        params.config.activeFields.currency_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                decimal_places: { name: "decimal_places", type: "int" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                decimal_places: makeActiveField(),
            },
        };
        params.config.activeFields.foreign_currency_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                decimal_places: { name: "decimal_places", type: "int" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                decimal_places: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids = makeActiveField();
        params.config.activeFields.line_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                name: { name: "name", type: "char" },
                balance: { name: "balance", type: "monetary" },
                amount_currency: { name: "amount_currency", type: "monetary" },
                currency_id: { name: "currency_id", type: "many2one" },
                currency_rate: { name: "currency_rate", type: "float" },
                is_same_currency: { name: "is_same_currency", type: "boolean" },
                company_currency_id: { name: "company_currency_id", type: "many2one" },
                account_id: { name: "account_id", type: "many2one" },
                partner_id: { name: "partner_id", type: "many2one" },
                move_id: { name: "move_id", type: "many2one" },
                first_reconciled_lines_id: { name: "first_reconciled_lines_id", type: "many2one" },
                count_reconciled_lines: { name: "count_reconciled_lines", type: "int" },
                first_reconciled_lines_excluding_exchange_diff_id: {
                    name: "first_reconciled_lines_excluding_exchange_diff_id",
                    type: "many2one",
                },
                count_reconciled_lines_excluding_exchange_diff: {
                    name: "count_reconciled_lines_excluding_exchange_diff",
                    type: "int",
                },
                exchange_move_ids: { name: "exchange_move_ids", type: "many2many" },
                reconcile_model_id: { name: "reconcile_model_id", type: "many2one" },
                has_invalid_analytics: { name: "has_invalid_analytics", type: "boolean" },
                analytic_distribution: { name: "analytic_distribution", type: "jsonb" },
                tax_line_id: { name: "tax_line_id", type: "many2one" },
                tax_ids: { name: "tax_ids", type: "many2many" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                name: makeActiveField(),
                balance: makeActiveField(),
                amount_currency: makeActiveField(),
                currency_id: makeActiveField(),
                currency_rate: makeActiveField(),
                is_same_currency: makeActiveField(),
                company_currency_id: makeActiveField(),
                account_id: makeActiveField(),
                partner_id: makeActiveField(),
                move_id: makeActiveField(),
                first_reconciled_lines_id: makeActiveField(),
                count_reconciled_lines: makeActiveField(),
                first_reconciled_lines_excluding_exchange_diff_id: makeActiveField(),
                count_reconciled_lines_excluding_exchange_diff: makeActiveField(),
                exchange_move_ids: makeActiveField(),
                reconcile_model_id: makeActiveField(),
                has_invalid_analytics: makeActiveField(),
                analytic_distribution: makeActiveField(),
                tax_line_id: makeActiveField(),
                tax_ids: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.reconcile_model_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                is_asking_for_autopost: { name: "is_asking_for_autopost", type: "boolean" },
                use_count: { name: "use_count", type: "integer" },
                created_automatically: { name: "created_automatically", type: "boolean" },
                rule_type: { name: "rule_type", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                is_asking_for_autopost: makeActiveField(),
                use_count: makeActiveField(),
                created_automatically: makeActiveField(),
                rule_type: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.exchange_move_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                amount_total_signed: { name: "amount_total_signed", type: "float" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                amount_total_signed: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.first_reconciled_lines_id.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    display_name: { name: "display_name", type: "char" },
                    move_name: { name: "move_name", type: "char" },
                    move_id: { name: "move_id", type: "many2one" },
                    full_reconcile_id: { name: "full_reconcile_id", type: "many2one" },
                    amount_currency: { name: "amount_currency", type: "monetary" },
                    currency_id: { name: "currency_id", type: "many2one" },
                },
                activeFields: {
                    id: makeActiveField(),
                    display_name: makeActiveField(),
                    move_name: makeActiveField(),
                    move_id: makeActiveField(),
                    full_reconcile_id: makeActiveField(),
                    amount_currency: makeActiveField(),
                    currency_id: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.first_reconciled_lines_excluding_exchange_diff_id.related =
            {
                fields: {
                    id: { name: "id", type: "int" },
                    move_name: { name: "move_name", type: "char" },
                    move_id: { name: "move_id", type: "many2one" },
                },
                activeFields: {
                    id: makeActiveField(),
                    move_name: makeActiveField(),
                    move_id: makeActiveField(),
                },
            };
        params.config.activeFields.line_ids.related.activeFields.move_id.related = {
            fields: {
                review_state: { name: "review_state", type: "char" },
            },
            activeFields: {
                review_state: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.tax_ids.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.partner_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                property_account_receivable_id: {
                    name: "property_account_receivable_id",
                    type: "many2one",
                },
                property_account_payable_id: {
                    name: "property_account_payable_id",
                    type: "many2one",
                },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                property_account_receivable_id: makeActiveField(),
                property_account_payable_id: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids.related.activeFields.account_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                display_name: { name: "display_name", type: "char" },
                account_type: { name: "account_type", type: "char" },
                reconcile: { name: "reconcile", type: "boolean" },
            },
            activeFields: {
                id: makeActiveField(),
                display_name: makeActiveField(),
                account_type: makeActiveField(),
                reconcile: makeActiveField(),
            },
        };
        params.config.activeFields.journal_id = makeActiveField();
        params.config.activeFields.journal_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                suspense_account_id: { name: "suspense_account_id", type: "many2one" },
                default_account_id: { name: "default_account_id", type: "many2one" },
                currency_id: { name: "currency_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                suspense_account_id: makeActiveField(),
                default_account_id: makeActiveField(),
                currency_id: makeActiveField(),
            },
        };
        params.config.activeFields.company_id = makeActiveField();
        params.config.activeFields.company_id.related = {
            fields: {
                id: { name: "id", type: "int" },
                currency_id: { name: "currency_id", type: "many2one" },
            },
            activeFields: {
                id: makeActiveField(),
                currency_id: makeActiveField(),
            },
        };
        params.config.activeFields.has_attachments = makeActiveField();
        params.config.activeFields.has_invalid_analytics = makeActiveField();
        params.config.activeFields.reconciled_lines_name = makeActiveField();
        params.limit = 40;
        return params;
    }
}
