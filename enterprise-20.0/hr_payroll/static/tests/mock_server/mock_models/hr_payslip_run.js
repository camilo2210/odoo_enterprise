import { fields, models } from "@web/../tests/web_test_helpers";

export class HrPayslipRun extends models.ServerModel {
    _name = "hr.payslip.run";

    name = fields.Char();
    date_start = fields.Date();
    date_end = fields.Date();
    currency_id = fields.Many2one({ relation: "res.currency" });
    state = fields.Selection({
        selection: [
            ["00_draft", "Draft"],
            ["01_ready", "Ready"],
            ["02_close", "Close"],
            ["03_paid", "Paid"],
        ],
    });

    _views = {
        "kanban,1": `
            <kanban js_class="payslip_run_kanban">
                <field name="currency_id"/>
                <templates>
                    <t t-name="menu" class="d-flex flex-column">
                        <button name="action_validate" type="object" class="btn oe_highlight" string="Validate"/>
                    </t>
                    <t t-name="card">
                        <field name="name"/>
                        <field name="date_start"/>
                        <field name="date_end"/>
                        <field name="state"/>
                    </t>
                </templates>
            </kanban>
        `,
    };

    _records = [
        {
            id: 1,
            name: "Basic Pay Run",
            state: "00_draft",
            currency_id: 1,
            display_name: "Basic Pay Run",
        },
    ];
}
