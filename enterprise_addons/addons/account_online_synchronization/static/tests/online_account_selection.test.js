import { expect, describe, test } from "@odoo/hoot";
import { mountView, defineModels, fields, models } from "@web/../tests/web_test_helpers";
import { queryAll, queryText } from "@odoo/hoot-dom";
import { mailModels } from "@mail/../tests/mail_test_helpers";

class AccountOnlineLink extends models.Model {
    _name = "account.online.link";

    id = fields.Integer();
    name = fields.Char();

    _records = [
        {
            id: 1,
            name: "Fake Bank",
        },
    ];
}

class AccountBankSelection extends models.Model {
    _name = "account.bank.selection";

    id = fields.Integer();
    account_online_link_id = fields.Many2one({ relation: "account.online.link" });
    account_online_account_ids = fields.One2many({ relation: "account.online.account" });

    _records = [
        {
            id: 1,
            account_online_link_id: 1,
            account_online_account_ids: [1, 2],
        },
    ];
}

class AccountOnlineAccount extends models.Model {
    _name = "account.online.account";

    id = fields.Integer();
    name = fields.Char();
    account_number = fields.Char();
    balance = fields.Integer();
    account_online_link_id = fields.Many2one({ relation: "account.online.link" });
    currency_id = fields.Many2one({ relation: "res.currency" });

    _records = [
        {
            id: 1,
            name: "account_1",
            balance: 10.0,
            account_number: "account_number_1",
            account_online_link_id: 1,
            currency_id: 1,
        },
        {
            id: 2,
            name: "account_2",
            balance: 20.0,
            account_number: "account_number_2",
            account_online_link_id: 1,
            currency_id: 1,
        },
    ];
}

class Currency extends models.Model {
    _name = "res.currency";

    name = fields.Char();
    symbol = fields.Char({ string: "Currency Sumbol" });

    _records = [{ id: 1, name: "USD", symbol: "$" }];
}

defineModels({
    ...mailModels,
    AccountOnlineLink,
    AccountBankSelection,
    AccountOnlineAccount,
    Currency,
});

describe.current.tags("desktop");

test("Account bank selection widget", async () => {
    await mountView({
        resModel: "account.bank.selection",
        type: "form",
        resId: 1,
        arch: `
            <form>
                <field name="account_online_account_ids" widget="online_account_selection"/>
            </form>
        `,
    });

    const cards = queryAll(".card");
    expect(cards.length).toBe(2);
    const firstTitle = queryAll(".card > .card-body > div > .card-title")[0];
    expect(queryText(firstTitle)).toBe("account_1");
    const firstAccountNumber = queryAll(".card > .card-body > div > .card-text")[0];
    expect(queryText(firstAccountNumber)).toBe("account_number_1");
    const balance = queryAll(".card > .card-body > div")[1];
    expect(queryText(balance)).toBe("$ 10.00");
});
