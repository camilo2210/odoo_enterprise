import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ImportAction } from "@base_import/import_action/import_action";
import { useBankStatementCSVImportModel } from "./bank_statement_csv_import_model";
import { x2ManyCommands } from "@web/core/orm_plugin";

export class BankStatementImportAction extends ImportAction {
    setup() {
        super.setup();

        this.orm = useService("orm");

        this.model = useBankStatementCSVImportModel({
            env: this.env,
            context: this.props.action.params.context || {},
        });

        this.env.config.setDisplayName(_t("Import Bank Statement")); // Displayed in the breadcrumbs
        this.state.filename = this.props.action.params.filename || undefined;

        onWillStart(async () => {
            if (this.props.action.params.context) {
                this.model.id = this.props.action.params.context.wizard_id;
                await this.model.init();
                await super.handleFilesUpload([{ name: this.state.filename }])
            }
        });
    }

    async openRecords(resIds) {
        if (this.model.statement_id) {
            const res = await this.orm.call(
                "account.bank.statement",
                "action_open_bank_reconcile_widget",
                [this.model.statement_id]
            );
            return this.actionService.doAction(res);
        }
        const statementLines = await this.orm.searchRead(
            "account.bank.statement.line",
            [["id", "in", resIds]],
            ["statement_id", "journal_id"]
        );
        const statementIds = Array.from(
            new Set(statementLines.map((statementLine) => statementLine.statement_id[0]))
        );
        await this.orm.write("account.bank.statement", statementIds, {
            attachment_ids: this.props.action.params.context.attachment_ids.map((attachment) =>
                x2ManyCommands.link(attachment)
            ),
        });
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Imported records"),
            res_model: "account.bank.statement.line",
            view_mode: "kanban,list",
            views: [
                [false, "kanban"],
                [false, "list"],
            ],
            target: "current",
            path: "imported-records",
            context: {
                search_default_imported_statement_lines: 1,
                search_default_journal_id: statementLines[0].journal_id[0],
                imported_transaction_ids: resIds,
            },
        });
    }
}

registry.category("actions").add("import_bank_stmt", BankStatementImportAction);
