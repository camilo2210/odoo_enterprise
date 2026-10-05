import { registry } from "@web/core/registry";
/*
    Tour for Search on Pay Runs 
        (Checking pay structure filtering)
        (Checking employee search in pay runs)
*/
registry.category("web_tour.tours").add('payroll_payrun_search_tour', {
    steps: () => [
    {
        content: "Open Payroll App",
        trigger: '.o_app[data-menu-xmlid="hr_payroll.menu_hr_payroll_root"]',
        run: "click",
    },
    {
        content: "Click Payslips",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
        run: "click",
    },
    {
        content: "Click Pay Runs",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payslip_run"]',
        run: "click",
    },
    {
        content: "Click New Button",
        trigger: 'button.btn-primary:contains("New")',
        run: "click",
    },
    {
        content: "Open Select Salary Structure",
        trigger: "input[id*=structure_id]",
        run: "click",
    },
    {
        content: "Select the Salary Structure for Test Regular Pay",
        trigger: '.o_field_many2one_selection .dropdown-item:contains("Test Regular Pay")',
        run: "click",
    },
    {
        content: "Open Start of the Period",
        trigger: 'button[data-field="date_start"]',
        run: "click",
    },
    {
        content: "Pass to the Next Month in Calendar",
        trigger: 'i[title="Next month"]',
        run: "click",
    },
    {
        content: "Select the 17th Day of Month",
        trigger: '.o_date_item_cell:contains("17")',
        run: "click",
    },
    {
        content: "Click to a Continue Button",
        trigger: 'button.btn-primary:contains("Continue")',
        run: "click",
    },
    {
        content: 'Ensure Employee Faruk is There',
        trigger: 'td[name="name"]:contains("Faruk")',
    },
    {
        content: 'Select the Record for Faruk',
        trigger: 'tr:has(td[name="name"]:contains("Faruk")) .o-checkbox',
        run: 'click',
    },
    {
        content: 'Press to Select Button',
        trigger: 'button.btn-primary:contains("Select")',
        run: 'click',
    },
    {
        content: "Wait",
        trigger: "body", 
        run: async function () {
            await new Promise((resolve) => setTimeout(resolve, 1000));
        },
    },
     {
        content: "Click Payslips",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
        run: "click",
    },
    {
        content: 'Return Back to Pay Runs',
        trigger: '.o-dropdown-item:contains("Pay Runs")',
        run: 'click',
    },
    {
        content: 'Check if Searched Pay Run Exists Before Search',
        trigger: '.o_kanban_record:contains("(BE)"), .o_data_row',
    },
    {
        content: 'Click to Search Bar',
        trigger: '.o_searchview_input:visible',
        run: 'click', 
    },
    {
        content: 'Write Faruk to Search Bar',
        trigger: '.o_searchview_input:visible',
        run: 'edit Faruk', 
    },
    {
        content: 'Wait for Search Bar to Have Value',
        trigger: '.o_searchview_input:value("Faruk")', 
    },
    {
        content: 'Search Employee for Faruk',
        trigger: '.o_searchview_autocomplete:visible .o-dropdown-item:contains("Employee")',
        run: 'click',
    }, 
    {
        content: 'Check if Searched Pay Run Exists',
        trigger: '.o_kanban_record:contains("(BE)"), .o_data_row',
    },
    {
        content: "Click Payslips",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payroll_payslips"]',
        run: "click",
    },
    {
        content: "Click Pay Runs",
        trigger: '[data-menu-xmlid="hr_payroll.menu_hr_payslip_run"]',
        run: "click",
    },
    {
        content: "Wait for Page and Search Bar", 
        trigger: "body", 
        run: async function () {
            await new Promise((resolve) => setTimeout(resolve, 1000));
        },
    },
    {
        content: 'Write Test Regular Pay to Search Bar',
        trigger: '.o_searchview_input',
        run: 'edit Test Regular Pay', 
    },
    {
        content: "Wait for Name Change", 
        trigger: "body", 
        run: async function () {
            await new Promise((resolve) => setTimeout(resolve, 1000));
        },
    },
    {
        content: 'Wait for Search Bar to Have Value',
        trigger: '.o_searchview_input:value("Test Regular Pay")', 
    },
    {
        content: 'Pay Structure Option is Available in the Autocomplete Dropdown Menus',
        trigger: '.o_searchview_autocomplete:visible .o-dropdown-item:contains("Pay Structure")',
    }, 
    {
        content: "Wait Until Dropdown is Clickable", 
        trigger: "body", 
        run: async function () {
            await new Promise((resolve) => setTimeout(resolve, 1000));
        },
    },
    {
        content: 'Search by Pay Structure - Test Regular Pay',
        trigger: '.o_searchview_autocomplete:visible .dropdown-item:contains("Pay Structure")',
        run: 'click',
    }, 
    {
        content: 'Check if Searched Pay Run Exists (Pay Run Test)',
        trigger: '.o_kanban_record:contains("(BE)"), .o_data_row',
    },
]});
