import { mailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, keyDown, queryAll, queryAllTexts, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { BankRecSelectCreateDialog } from "@account_accountant/components/bank_reconciliation/search_dialog/search_dialog";

class AccountMoveLine extends models.Model {
    move_name = fields.Char({ string: "Move Name" });
    ref = fields.Char({ string: "Ref" });
    date = fields.Date({ string: "Date" });
    partner_id = fields.Many2one({ string: "Partner", relation: "partner" });
    amount_residual = fields.Float({ string: "Amount Residual" });
    amount_residual_currency = fields.Float({ string: "Amount Residual Currency" });
    currency_id = fields.Many2one({ string: "Currency", relation: "res.currency" });
    company_currency_id = fields.Many2one({ string: "Currency", relation: "res.currency" });

    _records = [
        {
            id: 1,
            move_name: "INV/2025/0001",
            ref: "Customer Reference invoice 1",
            date: "2025-01-11",
            partner_id: 1,
            amount_residual: -230,
            currency_id: 1,
        },
        {
            id: 2,
            move_name: "INV/2025/0002",
            ref: "Customer Reference invoice 2",
            date: "2025-01-12",
            partner_id: 1,
            amount_residual: -150,
            currency_id: 1,
        },
        {
            id: 3,
            move_name: "INV/2025/0003",
            ref: "Customer Reference invoice 3",
            date: "2025-01-13",
            partner_id: 1,
            amount_residual: -50,
            currency_id: 1,
        },
        {
            id: 4,
            move_name: "INV/2025/0004",
            ref: "Customer Reference invoice 4",
            date: "2025-01-14",
            partner_id: 2,
            amount_residual: -100,
            currency_id: 1,
        },
        {
            id: 5,
            move_name: "INV/2025/0005",
            ref: "Customer Reference invoice 5",
            date: "2025-01-15",
            partner_id: 2,
            amount_residual: 100,
            currency_id: 1,
        },
        {
            id: 6,
            move_name: "INV/2025/0006",
            ref: "Customer Reference invoice 6",
            date: "2025-01-15",
            partner_id: 3,
            amount_residual: -125,
            currency_id: 1,
        },
    ];

    _views = {
        kanban: /* xml */ `
            <kanban js_class="bank_rec_dialog_kanban">
                <field name="currency_id"/>
                <field name="company_currency_id"/>
                <templates>
                    <t t-name="card">
                        <field name="move_name"/>
                        <field name="ref"/>
                        <field name="date"/>
                        <field name="partner_id"/>
                        <field name="amount_residual"/>
                        <field name="amount_residual_currency"/>
                    </t>
                </templates>
            </kanban>
        `,
        search: /* xml */ `
            <search>
                <field name="partner_id"/>
            </search>
        `,
    };
}

class Partner extends models.Model {
    name = fields.Char({ string: "Name" });

    _records = [
        { id: 1, name: "Jean Pierre" },
        { id: 2, name: "Pierre Jean" },
        { id: 3, name: "JB Pokie" },
    ];
}

defineModels({ ...mailModels, AccountMoveLine, Partner });

beforeEach(() => {
    mockDate("2025-04-22 00:00:00");
});

describe.current.tags("mobile");

test("BankRecSelectCreateDialog header with right information", async () => {
    await mountWithCleanup(WebClient);
    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 233.33,
            currency_id: { id: 1 },
            company_currency_id: { id: 1 },
        },
        date: luxon.DateTime.now(),
        reference: "A cool reference to display",
        context: {},
        domain: [],
    });
    await animationFrame();

    const bankReconciliationInfoNode = queryOne("div[name='bank_reconciliation_info']").children;
    const bankReconciliationInfo = queryAllTexts(bankReconciliationInfoNode);
    expect(bankReconciliationInfo[0]).toBe("Apr 22");
    expect(bankReconciliationInfo[1]).toBe("A cool reference to display");
    expect(bankReconciliationInfo[2]).toBe("Balance: $ 233.33");
});

test("BankRecSelectCreateDialog kanban view single currency", async () => {
    await mountWithCleanup(WebClient);
    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 100,
            currency_id: { id: 1 },
            company_currency_id: { id: 1 },
        },
        reference: "A useless reference",
        date: luxon.DateTime.now(),
        context: { search_default_partner_id: 1 },
        domain: [],
    });
    await animationFrame();

    expect("div[name='remaining_amount']").toHaveText("Balance: $ 100.00");
    await click("div.o_control_panel_navigation > button > i[data-icon='search']");
    await animationFrame();
    expect("div.o_facet_values > small.o_facet_value").toHaveText("Jean Pierre");
    let articles = queryAll("article.o_kanban_record");
    expect(articles.length).toBe(3);

    await click("button.o_facet_remove");
    await animationFrame();
    articles = queryAll("article.o_kanban_record");
    expect(articles.length).toBe(6);

    await keyDown("Alt");
    await contains(articles[3]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 0.00");

    await keyDown("Alt");
    await contains(articles[3]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 100.00");

    await keyDown("Alt");
    await contains(articles[4]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 200.00");

    await keyDown("Alt");
    await contains(articles[4]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: $ 100.00");

    await keyDown("Alt");
    await contains(articles[0]).click();
    await animationFrame();
    await contains(`.o_select_domain`).click();
    await animationFrame();
    expect("div.o_selection_box").toHaveText("All 6 selected");
    expect("div[name='remaining_amount']").toHaveText("Balance: $ -455.00");
});

test("BankRecSelectCreateDialog kanban view multiple currencies", async () => {
    AccountMoveLine._records.push({
        id: 7,
        move_name: "INV/2025/0007",
        ref: "Customer Reference invoice 7",
        date: "2025-01-17",
        partner_id: 3,
        amount_residual: -100,
        amount_residual_currency: -200,
        currency_id: 2,
        company_currency_id: 1,
    });

    await mountWithCleanup(WebClient);

    getService("dialog").add(BankRecSelectCreateDialog, {
        noCreate: true,
        resModel: "account.move.line",
        suspenseAccountLine: {
            amount_currency: 100,
            currency_id: { id: 2 },
            company_currency_id: { id: 1 },
        },
        reference: "A useless reference",
        date: luxon.DateTime.now(),
        context: {},
        domain: [],
    });

    await animationFrame();

    expect("div[name='remaining_amount']").toHaveText("Balance: 100.00 €");
    const articles = queryAll("article.o_kanban_record");
    expect(articles.length).toBe(7);

    await keyDown("Alt");
    await contains(articles[6]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: -100.00 €");

    await keyDown("Alt");
    await contains(articles[6]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: 100.00 €");

    await keyDown("Alt");
    await contains(articles[3]).click();
    await animationFrame();
    expect("div[name='remaining_amount']").toHaveText("Balance: /");
});
