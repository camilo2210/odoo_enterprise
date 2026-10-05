import { expect, test } from "@odoo/hoot";
import {
	contains,
	defineModels,
	fields,
	models,
	mountView,
	onRpc,
} from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

class AccountBankStatementLine extends models.Model {
	transaction_details = fields.Json();

	_records = [
		{
			id: 1,
			transaction_details: {
				name: "Downpayment for your services",
				amount: 350,
				status: "posted",
				identifier: "cb38d10c-4c93-41c7-bbbb-e0f57745cf0a",
				counter_part: { name: "Azure Interior" },
				is_zero_balancing: false,
			},
		},
	];
}

defineModels({ ...mailModels, AccountBankStatementLine });

test.tags("desktop");
test("Check Formatted Transactions Details Widget on Desktop", async () => {

    onRpc(
        "account.bank.statement.line",
        "format_transaction_details",
        () => {
            return "<div><pre><b>name:</b> Downpayment for your services\n<b>amount:</b> 350.0\n<b>status:</b> posted\n<b>identifier:</b> cb38d10c-4c93-41c7-bbbb-e0f57745cf0a\n<b>counter_part:</b> \n  <b>name:</b> Azure Interior\n<b>is_zero_balancing:</b> False\n</pre></div>";
        }
    );

	await mountView({
		type: "list",
		resModel: "account.bank.statement.line",
		arch: `
            <list>
                <field name="transaction_details" widget="formatted_transaction_details"/>
            </list>`,
		resId: 1,
	});

    // no popover by default
	expect(".popover-content-wrapper").toHaveCount(0);

    // hover over search icon to see if popover appears
    await contains(".o_field_formatted_transaction_details [data-icon='search']").hover();
	expect(".popover-content-wrapper").toHaveCount(1);

	// the output should be expected markup formatted
	expect(".popover-content-wrapper").toHaveText("name: Downpayment for your services\namount: 350.0\nstatus: posted\nidentifier: cb38d10c-4c93-41c7-bbbb-e0f57745cf0a\ncounter_part: \n name: Azure Interior\nis_zero_balancing: False");

    // hover over popover to check that it still stays open
    await contains(".popover-content-wrapper").hover();
	expect(".popover-content-wrapper").toHaveCount(1);
});
