import { queryAll, queryFirst, waitUntil } from "@odoo/hoot-dom";
import { registry } from "@web/core/registry";

/** Values that should never be displayed: unformatted values and serialization markers. */
const INVALID_TEXT = /\bundefined\b|\bNaN\b|\[object Object\]|Invalid DateTime|XSD(?:SKIP|MISSING|GYEARMONTH)/;

function checkText(element, description) {
    const invalidText = element.textContent.match(INVALID_TEXT);
    if (invalidText) {
        throw new Error(`${description} displays "${invalidText[0]}"`);
    }
}

function checkTables(element, description) {
    for (const table of element.querySelectorAll("table")) {
        if (!table.querySelector("tbody tr")) {
            throw new Error(`${description} displays an empty table`);
        }
    }
}

/** Each tab of the declared salaries lists the salaries declared to one institution. */
async function checkSalaryData(description) {
    const widget = queryFirst(".o_form_view .o_field_declare_salary_widget .o_swissdec_widget");
    if (!widget) {
        return;
    }
    checkText(widget, description);
    for (const tab of widget.querySelectorAll(".o_notebook_headers .nav-link")) {
        const tabDescription = `${description}, ${tab.textContent.trim()} tab`;
        tab.click();
        await waitUntil(() => tab.classList.contains("active"));
        const page = widget.querySelector(".o_notebook_content");
        if (!page.querySelector("table tbody tr")) {
            throw new Error(`${tabDescription} displays no salary`);
        }
        checkTables(page, tabDescription);
        checkText(page, tabDescription);
    }
}

/** The status of each institution opens in a dialog. */
async function checkStatusNotifications(description) {
    const selector = ".o_form_view .o_field_one2many button[name=action_open_status_notification]";
    const count = queryAll(selector).length;
    for (let index = 0; index < count; index++) {
        const statusDescription = `${description}, status notifications ${index + 1}`;
        queryAll(selector)[index].click();
        const status = await waitUntil(() => queryFirst(".modal .o_field_swissdec_status_result"));
        if (!status.textContent.trim()) {
            throw new Error(`${statusDescription} are empty`);
        }
        checkText(status, statusDescription);
        queryFirst(".modal .btn-close").click();
        await waitUntil(() => !queryFirst(".modal"));
    }
}

function checkResults(description) {
    for (const field of queryAll(".o_form_view .o_field_swissdec_salary_result, .o_form_view .o_field_swissdec_status_result")) {
        checkTables(field, description);
        checkText(field, description);
    }
}

/** Browse the records with the pager, from the first one. */
async function checkEveryRecord() {
    const total = Number(queryFirst(".o_form_view .o_pager_limit").textContent);
    for (let position = 1; position <= total; position++) {
        await waitUntil(() => queryFirst(".o_form_view .o_pager_value")?.textContent.trim() === String(position));
        const description = queryFirst(".o_breadcrumb .o_last_breadcrumb_item")?.textContent.trim() || `Record ${position}`;
        await checkSalaryData(description);
        await checkStatusNotifications(description);
        checkResults(description);
        if (position < total) {
            queryFirst(".o_form_view .o_pager_next").click();
        }
    }
}

registry.category("web_tour.tours").add("l10n_ch_hr_payroll_swissdec_widgets", {
    steps: () => [
        {
            content: "Open the first record",
            trigger: ".o_list_view .o_data_row .o_data_cell",
            run: "click",
        },
        {
            content: "Check the Swissdec widgets of every record",
            trigger: ".o_form_view .o_pager_limit",
            timeout: 60000,
            run: checkEveryRecord,
        },
    ],
});

registry.category("web_tour.tours").add("l10n_ch_hr_payroll_swissdec_wage_statement", {
    steps: () => [
        {
            content: "Open the wage statements of the declaration",
            trigger: ".o_field_declare_salary_widget .o_notebook_headers .nav-link:contains(Wage Statements)",
            run: "click",
        },
        {
            content: "Generate the wage statement of the first employee",
            trigger: ".o_field_declare_salary_widget .o_notebook_content tbody button:contains(Wage Statement):first",
            run: "click",
        },
        {
            content: "The wage statement is posted in the chatter",
            trigger: ".o-mail-Chatter .o-mail-AttachmentCard:contains(Wage_statement_)",
        },
    ],
});
