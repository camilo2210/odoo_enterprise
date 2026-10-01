import { registry } from '@web/core/registry';

registry.category("web_tour.tours").add("hr_salary_calculator_tour", {
    steps: () => [
    {
        trigger: ".o-dropdown[data-menu-xmlid='hr_payroll\\.menu_hr_payroll_employees']",
        run: "click",
    },
    {
        trigger: ".o-dropdown-item[data-menu-xmlid='hr_contract_salary\\.menu_hr_payroll_salary_calculator']",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name='employee_id'] .o-autocomplete--input",
        run: "edit Moul Rayeb",
    },
    {
        trigger: ".o-autocomplete--dropdown-item:contains('Moul Rayeb')",
        run: "click",
    },
    {
        trigger: ".o_technical_modal .o_form_saved",
        content: "Wait for the form's autosave",
    },
    {
        trigger: ".o_field_widget[name='employee_id'] input:value('Moul Rayeb')",
        content: "ASSERTION: Check that the Employee field contains 'Moul Rayeb'",
    },
    {
        trigger: ".o_field_widget[name='budget_type'] input",
        run: "click"
    },
    {
        trigger: ".o-dropdown-item:contains('Yearly Employer Cost')",
        run: "click"
    },
    {
        trigger: ".o_field_widget[name='salary_amount'] input:value(104,400.00)",
        content: "ASSERTION: Check that the Salary field contains the correct wage",
    },
    {
        trigger: ".o_field_widget[name='structure_id'] input:value('Regular structure')",
        content: "ASSERTION: Check that the Pay Structure field is set correctly",
    },
    {
        trigger: ".o_field_widget[name='resource_calendar_id'] input:value('Standard 38 hours/week')",
        content: "ASSERTION: Check that the Pay Structure field is set correctly",
    },
    {
        trigger: ".o_technical_modal footer > div > button",
        run: "click",
    }
]
})
