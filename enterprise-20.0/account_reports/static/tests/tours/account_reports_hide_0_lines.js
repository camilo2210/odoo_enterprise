import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('account_reports_hide_0_lines', {
    steps: () => [
        {
            content: 'test if the Bank and Cash line is present (but the value is 0)',
            trigger: '.line_name:contains("Bank and Cash Accounts")',
            run: "click",
        },
        {
            content: 'test if the Current Year Unallocated Earnings line is present (but the value is 0)',
            trigger: '.line_name:contains("Current Year Unallocated Earnings")',
            run: "click",
        },
        {
            content: 'test if the Earnings line is present (but value is different from 0 and so should be there after the hide_0_lines',
            trigger: '.line_name:contains("Earnings")',
            run: "click",
        },
        {
            content: "Open options selector",
            trigger: "#filter_extra_options button",
            run: 'click',
        },
        {
            content: "Select the hide line at 0 option",
            trigger: ".dropdown-item:contains('Hide lines at 0')",
            run: 'click',
        },
        {
            content: 'test if the Earnings line is still present',
            trigger: '.line_name:contains("Earnings")',
            run: "click",
        },
        {
            content: 'test if the Bank and Cash line is not present',
            trigger: '.line_name:not(:contains("Bank and Cash Accounts"))',
            run: "click",
        },
        {
            content: 'test if the Current Year Unallocated Earnings line is not present',
            trigger: '.line_name:not(:contains("Current Year Unallocated Earnings"))',
            run: "click",
        },
        {
            content: "Click again to open the options selector",
            trigger: "#filter_extra_options button",
            run: 'click',
        },
        {
            content: "Select the hide lines at 0 option again",
            trigger: ".dropdown-item:contains('Hide lines at 0')",
            run: 'click',
        },
        {
            content: 'test again if the Bank and Cash line is present (but the value is 0)',
            trigger: '.line_name:contains("Bank and Cash Accounts")',
            run: () => null,
        },
    ]
});

registry.category("web_tour.tours").add('account_reports_hide_0_lines_with_string_columns', {
    steps: () => [
        {
            content: "Check if the 211000 Accounts Payable line is present (but the value is 0)",
            trigger: "td:contains('211000 Accounts Payable')",
            run: "click",
        },
        {
            content: "Check if the MISC item line is present with string values set up, but all amounts are at 0",
            trigger: "td:contains('Coucou les biloutes')",
        },
        {
            content: "Open options selector",
            trigger: "#filter_extra_options button",
            run: 'click',
        },
        {
            content: "Select the hide line at 0 option",
            trigger: ".dropdown-item:contains('Hide lines at 0')",
            run: 'click',
        },
        {
            content: "Check if the MISC item line is hidden",
            trigger: ":not(:visible):contains('Coucou les biloutes')",
        },
        {
            content: "Click again to open the options selector",
            trigger: "#filter_extra_options button",
            run: 'click',
        },
        {
            content: "Select the hide lines at 0 option again",
            trigger: ".dropdown-item:contains('Hide lines at 0')",
            run: 'click',
        },
        {
            content: "Check again if the MISC item line is present (but the value is 0)",
            trigger: "td:contains('Coucou les biloutes')",
        },
    ]
});
