import { expect, runAllTimers, test } from "@odoo/hoot";
import { clickFieldDropdownItem, contains, defineModels, fields, models, mountView, onRpc } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

class AccountBankStatement extends models.Model {
    name = fields.Char();
    _records = [
        { id: 1, name: "Statement 1" },
        { id: 2, name: "Statement 2" },
    ];
}

class AccountBankStatementLine extends models.Model {
    name = fields.Char();
    statement_id = fields.Many2one({ relation: "account.bank.statement" });
    attachment_ids = fields.Many2many({ relation: "ir.attachment" });
    bank_statement_attachment_ids = fields.Many2many({ relation: "ir.attachment" });
    partner_id = fields.Integer();
    line_ids = fields.Integer();
    journal_id = fields.Integer();
    company_id = fields.Integer();
    _records = [
        { id: 1, name: "Line 1", statement_id: 1 },
        { id: 2, name: "Line 2", statement_id: 1 },
    ];
}

defineModels({ ...mailModels, AccountBankStatement, AccountBankStatementLine });

test.tags("desktop");
test("bank_rec_list_many2one_multi_id widget works in multi-edit", async () => {
    expect.assertions(1);

    onRpc("account.reconcile.model", "get_available_reconcile_model_per_statement_line", () => ({}));
    onRpc("web_save", ({ args }) => {
        expect(args[1].statement_id).toBe(3);
    });
    await mountView({
        resModel: "account.bank.statement.line",
        type: "list",
        arch: `
            <list multi_edit="1" js_class="bank_rec_list">
                <field name="name"/>
                <field name="statement_id" widget="bank_rec_list_many2one_multi_id"/>
            </list>
        `,
    });

    await contains(".o_data_row:eq(0) .o_list_record_selector input").click();
    await contains(".o_data_row:eq(1) .o_list_record_selector input").click();
    await contains(".o_data_row:eq(0) [name='statement_id']").click();
    await contains("[name='statement_id'] input").edit("New Statement", { confirm: false });
    await runAllTimers();
    await clickFieldDropdownItem("statement_id", 'Create "New Statement"');

    // Confirm the multi-edit dialog
    await contains(".modal .btn-primary").click();
});
