import { registry } from "@web/core/registry";
import { makeActiveField } from "@web/model/relational_model/utils";
import { listView } from "@web/views/list/list_view";
import {
    AttachmentPreviewListController,
    AttachmentPreviewListRenderer,
} from "../../attachment_preview_list_view/attachment_preview_list_view";
import { useBankReconciliation } from "../bank_reconciliation_service";
import { BankRecControlPanel } from "../control_action/control_action";
import { BankRecModel } from "../kanban_renderer";

export class BankRecListController extends AttachmentPreviewListController {
    setup() {
        super.setup();
        this.bankReconciliation = useBankReconciliation();
    }

    get previewerStorageKey() {
        return "account.statement_line_pdf_previewer_hidden";
    }

    get modelParams() {
        const params = super.modelParams;
        // Only computed by the kanban otherwise, while the actions of the selected lines need them
        params.hooks.onRootLoaded = (root) =>
            this.bankReconciliation.computeAvailableReconcileModels(root.records);
        params.config.activeFields.bank_statement_attachment_ids = makeActiveField();
        params.config.activeFields.bank_statement_attachment_ids.related = {
            fields: {
                mimetype: { name: "mimetype", type: "char" },
            },
            activeFields: {
                mimetype: makeActiveField(),
            },
        };
        params.config.activeFields.attachment_ids = makeActiveField();
        params.config.activeFields.attachment_ids.related = {
            fields: {
                mimetype: { name: "mimetype", type: "char" },
            },
            activeFields: {
                mimetype: makeActiveField(),
            },
        };
        params.config.activeFields.partner_id = makeActiveField();
        params.config.activeFields.partner_id.related = {
            fields: {
                id: { name: "id", type: "int" },
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
                property_account_receivable_id: makeActiveField(),
                property_account_payable_id: makeActiveField(),
            },
        };
        params.config.activeFields.line_ids = makeActiveField();
        params.config.activeFields.line_ids.readonly = true;
        params.config.activeFields.line_ids.related = {
            fields: {
                reconcile_model_id: { name: "reconcile_model_id", type: "many2one" },
            },
            activeFields: {
                reconcile_model_id: makeActiveField(),
            },
        };
        params.config.activeFields.journal_id = makeActiveField();
        params.config.activeFields.journal_id.related = {
            fields: {
                suspense_account_id: { name: "suspense_account_id", type: "many2one" },
                default_account_id: { name: "default_account_id", type: "many2one" },
            },
            activeFields: {
                suspense_account_id: makeActiveField(),
                default_account_id: makeActiveField(),
            },
        };
        params.config.activeFields.company_id = makeActiveField();
        params.config.activeFields.company_id.related = {
            fields: {
                id: { name: "id", type: "int" },
            },
            activeFields: {
                id: makeActiveField(),
            },
        };
        return params;
    }

    async setSelectedRecord(accountBankStatementLineData) {
        this.attachmentPreviewState.selectedRecord = accountBankStatementLineData;
        if (accountBankStatementLineData.data?.attachment_ids.count) {
            await this.setThread(accountBankStatementLineData, "attachment_ids", "move_id");
        } else {
            await this.setThread(
                accountBankStatementLineData,
                "bank_statement_attachment_ids",
                "statement_id"
            );
        }
    }
}

export class BankRecListRenderer extends AttachmentPreviewListRenderer {}

export const bankRecListView = {
    ...listView,
    ControlPanel: BankRecControlPanel,
    Controller: BankRecListController,
    Renderer: BankRecListRenderer,
    Model: BankRecModel,
};

registry.category("views").add("bank_rec_list", bankRecListView);
