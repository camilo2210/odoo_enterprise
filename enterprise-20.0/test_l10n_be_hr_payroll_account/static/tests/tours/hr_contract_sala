import { registry } from "@web/core/registry";
import { redirect } from "@web/core/utils/urls";
import { stepUtils } from "@web_tour/tour_utils";
import { post } from "@web/core/network/http_service";

const salaryConfigTourStart = () => [
{
        content: "Go on configurator",
        trigger: ".navbar",
        run: function () {
            redirect("/odoo");
        },
        expectUnloadPage: true,
    },
    {
        content: "Log into Belgian Company",
        trigger: ".o_menu_systray .o_switch_company_menu",
        run: "click",
    },
    {
        content: "Log into Belgian Company",
        trigger:
            ".o-dropdown--menu .dropdown-item div span:contains('My Belgian Company - TEST')",
        run: "click",
        expectUnloadPage: true,
    },
    {
        trigger:
            ".o_menu_systray .o_switch_company_menu span:contains('My Belgian Company - TEST')",
    },
    {
        content: "Recruitment",
        trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
        run: "click",
    },
    {
        content: "Jobs list view",
        trigger: ".o_switch_view.o_list",
        run: "click",
    },
    {
        content: "Create Job Position",
        trigger: "button.o_list_button_add",
        run: "click",
    },
    {
        content: "Job's Name",
        trigger: ".o_field_widget[name='name'] textarea",
        run: "edit (Experienced Developer (BE))",
    },
    {
        content: "Select Recruitment Tab",
        trigger: ".o_notebook ul > li > button:contains(Details)",
        run: "click",
    },
    {
        content: "Contract Template",
        trigger: ".o_field_widget.o_field_many2one[name=contract_template_id] input",
        run: `edit New Developer Template Contract`,
    },
    {
        isActive: ["auto"],
        trigger: ".ui-autocomplete > li > a:contains(New Developer Template Contract)",
        run: "click",
    },
    {
        content: "Save Job",
        trigger: "button.o_form_button_save",
        run: "click",
    },
    {
        trigger: ".o_form_saved",
    },
    {
        content: "Open Application Pipe",
        trigger: "button.oe_stat_button:contains(Applications)",
        run: "click",
    },
    {
        trigger: '.o_breadcrumb .active:contains("Applications")',
    },
    {
        content: "Create Applicant",
        trigger: ".o-kanban-button-new",
        run: "click",
    },
    // Test Applicant
    {
        content: "Applicant's Name",
        trigger: '.oe_title [name="partner_name"] input',
        run: "edit Mitchell Admin 2",
    },
    {
        content: "Applicant's Email",
        trigger: '.o_group [name="email_from"] input',
        run: "edit mitchell2.stephen@example.com",
    },
    {
        trigger: ".o_statusbar_buttons",
    },
    {
        content: "Generate Offer",
        trigger: ".o_statusbar_buttons > button:contains('Generate Offer')",
        run: "click",
    },
    {
        content: "Open compose email wizard",
        trigger: "button[name='action_send_by_email']",
        run: "click",
    },
    {
        trigger: ".modal-dialog .btn-primary:contains('Send')",
    },
    {
        content: "Send Offer",
        trigger: "button.o_mail_send",
        run: "click",
    },
    {
        trigger: "button[name='action_jump_to_offer']",
    },
    {
        content: "Unlog + Go on Configurator",
        trigger: ".o-mail-Chatter .o-mail-Message:eq(0) a",
        async run(helpers) {
            const offer_link = helpers.anchor.href;
            // Retrieve the link without the origin to avoid
            // mismatch between localhost:8069 and 127.0.0.1:8069
            // when running the tour with chrome headless
            var regex = "/salary_package/simulation/.*";
            var url = offer_link.match(regex)[0];

            const redirect_url = await post('/web/session/logout?redirect=' + window.location.origin + url, { csrf_token: odoo.csrf_token }, "url");
            redirect(redirect_url);
        },
        expectUnloadPage: true,
    },
];

const salaryConfigTourPersonalInfo = () => [
    {
        trigger: 'span[name="Gross"][value="3000"]',
    },
    {
        content: "Name",
        trigger: 'input[name="name"]',
        run: "edit Nathalie",
    },
    {
        content: "BirthDate",
        trigger: '[name="birthday"] input',
        run: function () {
            this.anchor.value = "1997-09-01";
        },
    },
    {
        content: "sex",
        trigger: '[name="sex"] input[value="female"]:not(:visible)',
        run: "check",
    },
    {
        content: "National Identification Number",
        trigger: 'input[name="niss"]',
        run: "edit 97.09.01-250.74",
    },
    {
        content: "Street",
        trigger: 'input[name="private_street"]',
        run: "edit Rue des Wallons",
    },
    {
        content: "City",
        trigger: 'input[name="private_city"]',
        run: "edit Louvain-la-Neuve",
    },
    {
        content: "Zip Code",
        trigger: 'input[name="private_zip"]',
        run: "edit 1348",
    },
    {
        content: "Country",
        trigger: "select[name=private_country_id]:not(:visible)",
        run: "selectByLabel Belgium",
    },
    {
        content: "Email",
        trigger: 'input[name="private_email"]',
        run: "edit nathalie.stephen@example.com",
    },
    {
        content: "Phone Number",
        trigger: 'input[name="private_phone"]',
        run: "edit 1234567890",
    },
    {
        content: "Place of Birth",
        trigger: 'input[name="place_of_birth"]',
        run: "edit Brussels",
    },
    {
        content: "KM Home/Work",
        trigger: 'input[name="km_home_work"]',
        run: "edit 75",
    },
    {
        content: "Certificate",
        trigger: "select[name=certificate]:not(:visible)",
        run: "selectByLabel Master",
    },
    {
        content: "School Level",
        trigger: 'input[name="study_field"]',
        run: "edit Civil Engineering, Applied Mathematics",
    },
    {
        content: "Set Seniority at Hiring",
        trigger: 'input[name="l10n_be_scale_seniority"]',
        run: "edit 1",
    },
    {
        content: "Bank Account",
        trigger: 'input[name="account_number"]',
        run: "edit BE10 3631 0709 4104",
    },
    {
        content: "Account Holder Name",
        trigger: 'input[name="holder_name"]',
        run: "edit Mitchell Admin 2"
    },
    {
        content: "Emergency Contact",
        trigger: 'input[name="emergency_contact"]',
        run: "edit Batman",
    },
    {
        content: "Emergency Phone",
        trigger: 'input[name="emergency_phone"]',
        run: "edit +32 2 290 34 90",
    },
    {
        content: "Nationality",
        trigger: "select[name=country_id]:not(:visible)",
        run: "selectByLabel Belgium",
    },
    {
        content: "Country of Birth",
        trigger: "select[name=country_of_birth]:not(:visible)",
        run: "selectByLabel Belgium",
    },
    {
        content: "Lang",
        trigger: "select[name=lang]:not(:visible)",
        run: "selectByLabel English",
    },
    {
        content: "Choose a car",
        trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
        run: "click",
    },
    {
        content: "Choose a new car",
        trigger: `select[name="select_company_car_total_depreciated_cost"]:not(:visible)`,
        run: "selectByLabel a3",
    },
    // set personal info
    {
        content: "Upload ID card copy (Both Sides)",
        trigger: 'input[name="id_card"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_id_card.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="id_card"]', [file]);
        },
    },
    {
        content: "Upload Mobile Subscription Invoice",
        trigger: 'input[name="mobile_invoice"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_mobile_invoice.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="mobile_invoice"]', [file]);
        },
    },
    {
        content: "Upload Sim Card Copy",
        trigger: 'input[name="sim_card"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_sim_card.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="sim_card"]', [file]);
        },
    },
    {
        content: "Upload Internet Subscription invoice",
        trigger: 'input[name="internet_invoice"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_internet_invoice.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="internet_invoice"]', [file]);
        },
    },
    {
        content: "Upload Driving License",
        trigger: 'input[name="driving_license"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_driving_license.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="driving_license"]', [file]);
        },
    },
    {
        trigger: 'span[name="Gross"][value="2671.14"]',
    },
    {
        content: "Take Extra-Legal Leaves",
        trigger: 'input[list="holidays_range"]',
        run: "range 3",
    },
    {
        content: "Set Public Transportation Amount",
        trigger: 'input[name="bus_transport_reimbursed_amount_manual"]',
        run: "edit 100 && click label:contains(Bus)",
    },
    {
        content: "Set Public Transportation Amount",
        trigger: 'input[name="bus_transport_employee_kilometer_manual"]',
        run: "edit 10 && click label:contains(Bus)",
    },
    {
        trigger: 'span[name="Gross"][value="2599.71"]',
    },
];

const salaryConfigTourSubmitAndSign = () => [
    {
        content: "submit",
        trigger: "button#hr_cs_submit",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Next 1",
        trigger: ":iframe .o_sign_sign_item_navigator",
        run: "click",
    },
    {
        content: "Type Date",
        trigger: ":iframe input.ui-selected",
        run: "edit 09/17/2018",
    },
    // fill signature
    {
        content: "Next 3",
        trigger: ":iframe .o_sign_sign_item_navigator",
        run: "click",
    },
    {
        content: "Click Signature",
        trigger: ":iframe button.o_sign_sign_item",
        run: "click",
    },
    {
        content: "Click Auto",
        trigger: "a.o_web_sign_auto_button:contains('Auto')",
        run: "click",
    },
    {
        content: "Adopt & Sign",
        trigger: "footer.modal-footer button.btn-primary:enabled",
        run: "click",
    },
    {
        content: "Wait modal closed",
        trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
    },
    // fill date
    {
        content: "Next 4",
        trigger: ':iframe .o_sign_sign_item_navigator:contains("next")',
        run: "click",
    },
    {
        content: "Type Date",
        trigger: ":iframe input.ui-selected",
        run: "edit 09/17/2018",
    },
    {
        content: "Validate and Sign",
        trigger: ".o_sign_validate_banner button",
        run: "click",
    },
];

registry.category("web_tour.tours").add("hr_contract_salary_tour", {
    steps: () => [
        ...salaryConfigTourStart(),
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Choose a car",
            trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="2671.14"]',
        },
        {
            content: "Unchoose a car",
            trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Set Public Transportation Amount",
            trigger: 'input[name="bus_transport_reimbursed_amount_manual"]',
            run: "edit 100 && click label:contains(bus)",
        },
        {
            content: "Set Public Transportation Amount",
            trigger: 'input[name="bus_transport_employee_kilometer_manual"]',
            run: "edit 10 && click label:contains(bus)",
        },
        {
            trigger: 'span[name="Gross"][value="2961.69"]',
        },
        {
            content: "Unchoose Public Transportation",
            trigger: 'input[name="bus_transport_reimbursed_amount_manual"]',
            run: "edit 0 && click label:contains(bus)",
        },
        {
            content: "Unchoose Public Transportation",
            trigger: 'input[name="bus_transport_employee_kilometer_manual"]',
            run: "edit 0 && click label:contains(bus)",
        },
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Set Train Transportation Amount",
            trigger: 'input[name="train_transport_reimbursed_amount_manual"]',
            run: "edit 60 && click label:contains(train)",
        },
        {
            trigger: 'span[name="Gross"][value="2913.05"]',
        },
        {
            content: "Unchoose Train Transportation",
            trigger: 'input[name="train_transport_reimbursed_amount_manual"]',
            run: "edit 0 && click label:contains(train)",
        },
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Set Private Car Transportation Amount",
            trigger: 'input[name="private_car_reimbursed_amount_manual"]',
            run: "edit 150 && click label:contains(private)",
        },
        {
            trigger: 'span[name="Gross"][value="2892.42"]',
        },
        {
            content: "Change km_home_work on personal info",
            trigger: 'input[name="private_car_reimbursed_amount_manual"]',
            run: "edit 75 && click label:contains(Transportation)",
        },
        {
            trigger: 'span[name="Gross"][value="2934.17"]',
        },
        {
            content: "Reset 150 km",
            trigger: 'input[name="private_car_reimbursed_amount_manual"]',
            run: "edit 150 && click label:contains(Transportation)",
        },
        {
            trigger: 'span[name="Gross"][value="2892.42"]',
        },
        {
            content: "Unchoose Private Car Transportation",
            trigger: 'input[name="private_car_reimbursed_amount_manual"]',
            run: "edit 0 && click label:contains(Transportation)",
        },
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Choose a Bike",
            trigger: "input[name=fold_company_bike_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="2982.81"]',
        },
        {
            content: "Choose Bike 2",
            trigger: "select[name=select_company_bike_depreciated_cost]:not(:visible)",
            run: "selectByLabel Bike 2",
        },
        {
            trigger: 'span[name="Gross"][value="2965.61"]',
        },
        {
            content: "Choose Bike 1",
            trigger: "select[name=select_company_bike_depreciated_cost]:not(:visible)",
            run: "selectByLabel Bike 1",
        },
        {
            trigger: 'span[name="Gross"][value="2982.81"]',
        },
        {
            content: "Unchoose Bike",
            trigger: "input[name=fold_company_bike_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Unset Internet",
            trigger: 'input[name="internet_manual"]',
            run: "edit 0 && click label:contains(Internet)",
        },
        {
            trigger: 'span[name="Gross"][value="3026.13"]',
        },
        {
            content: "Reset Internet",
            trigger: 'input[name="internet_manual"]',
            run: "edit 38 && click label:contains(Internet)",
        },
        // In order to choose Fuel card, the mandatory advantage, company car, should be selected first
        {
            trigger: 'span[name="Gross"][value="3000"]',
        },
        {
            content: "Choose a car",
            trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="2671.14"]',
        },
        {
            content: "Take Fuel Card",
            trigger: 'input[list="fuel_card_range"]',
            run: "range 250",
        },
        {
            trigger: 'span[name="Gross"][value="2499.2"]',
        },
        {
            content: "Untake Fuel Card",
            trigger: 'input[list="fuel_card_range"]',
            run: "range 0",
        },
        {
            trigger: 'span[name="Gross"][value="2671.14"]',
        },
        {
            content: "Unchoose a car",
            trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
            run: "click",
        },
        ...salaryConfigTourPersonalInfo(),
        ...salaryConfigTourSubmitAndSign()

    ],
});

registry.category("web_tour.tours").add("hr_contract_salary_tour_sign_again", {
    steps: () => [
        {
            content: "Go on configurator",
            trigger: ".navbar",
            run: function () {
                redirect("/odoo");
            },
            expectUnloadPage: true,
        },
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu",
            run: "click",
        },
        {
            content: "Log into Belgian Company",
            trigger:
                ".o-dropdown--menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger:
                ".o_menu_systray .o_switch_company_menu span:contains('My Belgian Company - TEST')",
        },
        {
            content: "Recruitment",
            trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
            run: "click",
        },
        {
            content: "Open Job Position",
            trigger: ".o_kanban_record:contains('Experienced Developer (BE)')",
            run: "click",
        },
        {
            content: "Go to Applicant",
            trigger: ".o_kanban_group:nth-child(1) > .o_kanban_record > span:contains('Mitchell Admin 2')",
            run: "click",
        },
        {
            content: "Open Existing Offer",
            trigger: "button.oe_stat_button:contains(Offers)",
            run: "click",
        },
        {
            content: "Choose a car",
            trigger: "input[id=radio_field_1_available]",
            run: "click",
        },
        {
            content: "Save Offer",
            trigger: ".o_form_button_save",
            run: "click",
        },

        {
            content: "Unlog + Go on Configurator",
            trigger: ".o-mail-Chatter .o-mail-Message:eq(2) a",
            async run(helpers) {
                const offer_link = helpers.anchor.href;
                // Retrieve the link without the origin to avoid
                // mismatch between localhost:8069 and 127.0.0.1:8069
                // when running the tour with chrome headless
                var regex = "/salary_package/simulation/.*";
                var url = offer_link.match(regex)[0];

                const redirect_url = await post('/web/session/logout?redirect=' + window.location.origin + url, { csrf_token: odoo.csrf_token }, "url");
                redirect(redirect_url);
            },
            expectUnloadPage: true,
        },
        {
            trigger: 'span[name="Gross"][value="2941.75"]',
        },
        {
            content: "Choose a car",
            trigger: "input[name=fold_company_car_total_depreciated_cost]:not(:visible)",
            run: "click",
        },
        {
            content: "Check car name",
            trigger: "select[name='select_company_car_total_depreciated_cost']:not(:visible)",
            run: function () {
                const selectedCar = document.querySelector("select[name='select_company_car_total_depreciated_cost'] option");
                if (!selectedCar.innerText.includes('A3')) {
                    throw new Error("The car is not selected");
                }
            },
        },
        {
            trigger: 'span[name="Gross"][value="2617.16"]',
        },
        ...salaryConfigTourSubmitAndSign()
    ],
});

registry.category("web_tour.tours").add("hr_contract_salary_tour_hr_sign", {
    steps: () => [
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu",
            run: "click",
        },
        {
            content: "Log into Belgian Company",
            trigger:
                ".o-dropdown--menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger:
                ".o_menu_systray .o_switch_company_menu span:contains('My Belgian Company - TEST')",
        },
        {
            content: "Open Activity Systray",
            trigger: ".o-mail-ActivityMenu-counter",
            run: "click",
        },
        {
            content: "Open Sign Requests",
            trigger: '.o-dropdown--menu .list-group-item:contains("Signature")',
            run: "click",
        },
        {
            content: "Go to Signable Document",
            trigger: "button[name='go_to_signable_document']",
            run: "click",
        },
        {
            content: "Next 1",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Next 2",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Click Signature",
            trigger: ":iframe button.o_sign_sign_item",
            run: "click",
        },
        {
            content: "Click Auto",
            trigger: "a.o_web_sign_auto_button:contains('Auto')",
            run: "click",
        },
        {
            content: "Adopt & Sign",
            trigger: "footer.modal-footer button.btn-primary:enabled",
            run: "click",
        },
        {
            trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("hr_contract_salary_tour_2", {
    steps: () => [
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu",
            run: "click",
        },
        {
            content: "Log into Belgian Company",
            trigger:
                ".o-dropdown--menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger:
                ".o_menu_systray .o_switch_company_menu span:contains('My Belgian Company - TEST')",
        },
        {
            content: "Recruitment",
            trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
            run: "click",
        },
        {
            content: "Jobs list view",
            trigger: ".o_switch_view.o_list",
            run: "click",
        },
        {
            content: "Select Our Job",
            trigger: 'table.o_list_table tbody td:contains("Experienced Developer")',
            run: "click",
        },
        {
            trigger: ".o_form_saved",
        },
        {
            content: "Open Application Pipe",
            trigger: "button.oe_stat_button:contains(Applications)",
            run: "click",
        },
        {
            trigger: '.o_breadcrumb .active:contains("Applications")',
        },
        {
            content: "Create Applicant",
            trigger: ".o-kanban-button-new",
            run: "click",
        },
        {
            content: "Applicant Name",
            trigger: '.oe_title [name="partner_name"] input',
            run: "edit Mitchell Admin 3",
        },
        {
            content: "Add Email Address",
            trigger: '.o_group [name="email_from"] input',
            run: "edit mitchell2.stephen@example.com",
        },
        {
            content: "Confirm Applicant Creation",
            trigger: ".o_control_panel button.o_form_button_save",
            run: "click",
        },
        {
            content: "Click on the 'Contract Signed' bar button",
            trigger: 'button.o_arrow_button:contains("Contract Signed")',
            run: 'click',
        },
        {
            trigger: ".o_statusbar_buttons",
        },
        {
            content: "Create Employee",
            trigger: ".o_statusbar_buttons > button[name='create_employee_from_applicant']",
            run: "click",
        },
        {
            content: "Add Manager",
            trigger: ".nav-link:contains('Work')",
            run: "click",
        },
        {
            content: "Manager",
            trigger:
                ".o_field_widget.o_field_many2one_avatar_user.o_field_many2one_avatar[name=parent_id] input",
            run: `edit Mitchell`,
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains(Mitchell)",
            run: "click",
        },
        {
            content: "Add Work Email",
            trigger: '[name="work_email"] input',
            run: "edit mitchel3_work@example.com",
        },
        {
            trigger: '.o-mail-Message-body a[href*="/action-hr.plan_wizard_action"]',
        },
        {
            content: "Save Employee",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_form_saved",
        },
        {
            content: "Add Salary Structure",
            trigger: ".nav-link:contains('Payroll')",
            run: "click",
        },
        {
            content: "Salary Structure Type",
            trigger: ".o_field_widget.o_field_many2one[name=structure_type_id] input",
            run: `edit CP200 BE`,
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains('CP200 BE')",
            run: "click",
        },
        {
            content: "Add HR Responsible",
            trigger: ".nav-link:contains('Settings')",
            run: "click",
        },
        {
            content: "HR Responsible",
            trigger:
                "div.o_field_widget.o_required_modifier.o_field_many2one_avatar_user.o_field_many2one_avatar[name=hr_responsible_id] input",
            run: `edit Mitchell Admin`,
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains('Mitchell Admin')",
            run: "click",
        },
        {
            content: "Select Payroll Tab",
            trigger: ".o_notebook ul > li > button:contains(Payroll)",
            run: "click",
        },
        {
            content: "Contract Information",
            trigger: "div[name='wage'] input",
            run: "edit 2950",
        },
        {
            content: "Contract Information",
            trigger: ".o_field_widget.o_field_many2one[name=car_id] input",
            run: `edit JFC`,
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains('1-JFC-094')",
            run: "click",
        },
        {
            content: "Contract Information",
            trigger: "div[name='fuel_card'] input",
            run: "edit 250 && click div:contains(Monthly)",
        },
        {
            content: "Contract Information",
            trigger: "div[name='commission_on_target'] input",
            run: "edit 1000 && click div:contains(Monthly)",
        },
        {
            content: "Contract Information",
            trigger: "[name='ip_wage_rate'] input",
            run: "edit 25 && click div:contains(Monthly)",
        },
        {
            content: "Save Contract",
            trigger: ".o_form_button_save",
            run: "click",
        },
        stepUtils.autoExpandMoreButtons(),
        {
            content: "Generate Offer",
            trigger: ".btn:contains(Offers)",
            run: "click",
        },
        {
            content: "Select Contract",
            trigger: ".o_field_widget.o_field_many2one[name=sign_template_id] input",
            run: `edit test_employee_contract`,
        },
        {
            isActive: ["auto"],
            trigger: ".ui-autocomplete > li > a:contains('test_employee_contract')",
            run: "click",
        },
        {
            content: "Save Offer",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Open compose email wizard",
            trigger: "button[name='action_send_by_email']",
            run: "click",
        },
        {
            content: "Send Offer",
            trigger: "button.o_mail_send",
            run: "click",
        },
        {
            trigger: "button[name='action_jump_to_offer']",
        },
        {
            content: "Go on configurator",
            trigger: ".o-mail-Chatter .o-mail-Message:eq(0) a",
            run: function (helpers) {
                const offer_link = helpers.anchor.href;
                // Retrieve the link without the origin to avoid
                // mismatch between localhost:8069 and 127.0.0.1:8069
                // when running the tour with chrome headless
                var regex = "/salary_package/simulation/.*";
                var url = offer_link.match(regex)[0];
                window.location.href = window.location.origin + url;
            },
            expectUnloadPage: true,
        },
        {
            content: "wait for the interaction to load",
            trigger: "#hr_contract_salary[is-ready=true]",
        },
        {
        content: "Choose a new car",
        trigger: `select[name="select_company_car_total_depreciated_cost"]:not(:visible)`,
        run: "selectByLabel Opel",
        },
        {
            content: "BirthDate",
            trigger: 'input[name="birthday"]',
            run() {
                this.anchor.value = "1988-05-10";
            },
        },
        {
            content: "sex",
            trigger: "input[name=sex]:not(:visible)",
            run: function () {
                document.querySelector('input[value="female"]').checked = true;
            },
        },
        {
            content: "National Identification Number",
            trigger: 'input[name="niss"]',
            run: "edit 88.05.10-562.51",
        },
        {
            content: "Street",
            trigger: 'input[name="private_street"]',
            run: "edit Rue des Wallons",
        },
        {
            content: "City",
            trigger: 'input[name="private_city"]',
            run: "edit Louvain-la-Neuve",
        },
        {
            content: "Zip Code",
            trigger: 'input[name="private_zip"]',
            run: "edit 1348",
        },
        {
            content: "Email",
            trigger: 'input[name="private_email"]',
            run: "edit mitchell2.stephen@example.com",
        },
        {
            content: "Phone Number",
            trigger: 'input[name="private_phone"]',
            run: "edit 1234567890",
        },
        {
            content: "Place of Birth",
            trigger: 'input[name="place_of_birth"]',
            run: "edit Brussels",
        },
        {
            content: "KM Home/Work",
            trigger: 'input[name="km_home_work"]',
            run: "edit 75",
        },
        {
            trigger: "label[for=certificate]",
        },
        {
            content: "Certificate",
            trigger: "select[name=certificate]:not(:visible)",
            run: "selectByLabel Master",
        },
        {
            content: "School Level",
            trigger: 'input[name="study_field"]',
            run: "edit Civil Engineering, Applied Mathematics",
        },
        {
            content: "Set Seniority at Hiring",
            trigger: 'input[name="l10n_be_scale_seniority"]',
            run: "edit 1 && click body",
        },
        {
            trigger: "label[for=lang]:eq(0)",
        },
        {
            content: "Lang",
            trigger: "select[name=lang]:not(:visible)",
            run: "selectByLabel English",
        },
        {
            content: "Bank Account",
            trigger: 'input[name="account_number"]',
            run: "edit BE10 3631 0709 4104",
        },
        {
            content: "Account Holder Name",
            trigger: 'input[name="holder_name"]',
            run: "edit Mitchell Admin 2"
        },
        {
            content: "Bank Account",
            trigger: 'input[name="emergency_contact"]',
            run: "edit Batman",
        },
        {
            content: "Bank Account",
            trigger: 'input[name="emergency_phone"]',
            run: "edit +32 2 290 34 90",
        },
        {
            trigger: "label[for=country_id]:eq(0)",
        },
        {
            content: "Nationality",
            trigger: "select[name=country_id]:not(:visible)",
            run: "selectByLabel Belgium",
        },
        {
            content: "Country of Birth",
            trigger: "select[name=country_of_birth]:not(:visible)",
            run: "selectByLabel Belgium",
        },
        {
            trigger: "label[for=private_country_id]:eq(0)",
        },
        {
            content: "Country",
            trigger: "select[name=private_country_id]:not(:visible)",
            run: "selectByLabel Belgium",
        },
        {
            content: "Set 0 Children",
            trigger: "input[name=children]",
            run: "edit 0 && click body",
        },
        // set personal info
        {
        content: "Upload Driving License",
        trigger: 'input[name="driving_license"]',
        async run({ inputFiles }) {
            const file = new File(["hello, world"], "employee_driving_license.pdf", {
                type: "application/pdf",
            });
            await inputFiles('input[name="driving_license"]', [file]);
        },
        },
        {
            content: "Upload ID card copy (Both Sides)",
            trigger: 'input[name="id_card"]',
            async run({ inputFiles }) {
                const file = new File(["hello, world"], "employee_id_card.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="id_card"]', [file]);
            },
        },
        {
            content: "Upload Mobile Subscription Invoice",
            trigger: 'input[name="mobile_invoice"]',
            async run({ inputFiles }) {
                const file = new File(["hello, world"], "employee_mobile_invoice.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="mobile_invoice"]', [file]);
            },
        },
        {
            content: "Upload Sim Card Copy",
            trigger: 'input[name="sim_card"]',
            async run({ inputFiles }) {
                const file = new File(["hello, world"], "employee_sim_card.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="sim_card"]', [file]);
            },
        },
        {
            content: "Upload Internet Subscription invoice",
            trigger: 'input[name="internet_invoice"]',
            async run({ inputFiles }) {
                const file = new File(["hello, world"], "employee_internet_invoice.pdf", {
                    type: "application/pdf",
                });
                await inputFiles('input[name="internet_invoice"]', [file]);
            },
        },
        {
            content: "submit",
            trigger: "button#hr_cs_submit",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Next 6",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Type Date",
            trigger: ":iframe input.ui-selected",
            run: "edit 09/17/2018",
        },
        // fill signature
        {
            content: "Next 8",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Click Signature",
            trigger: ":iframe button.o_sign_sign_item",
            run: "click",
        },
        {
            content: "Click Auto",
            trigger: "a.o_web_sign_auto_button:contains('Auto')",
            run: "click",
        },
        {
            content: "Adopt & Sign",
            trigger: "footer.modal-footer button.btn-primary:enabled",
            run: "click",
        },
        {
            content: "Wait modal closed",
            trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
        },
        // fill date
        {
            content: "Next 9",
            trigger: ':iframe .o_sign_sign_item_navigator:contains("next")',
            run: "click",
        },
        {
            content: "Type Date",
            trigger: ":iframe input.ui-selected",
            run: "edit 09/17/2018",
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Go on configurator",
            trigger: "h1.hr_cs_brand_optional",
            run: function () {
                redirect("/odoo");
            },
            expectUnloadPage: true,
        },
        {
            content: "Check home page is loaded",
            trigger: "a.o_app.o_menuitem",
        },
    ],
});

registry.category("web_tour.tours").add("hr_contract_salary_tour_counter_sign", {
    steps: () => [
        {
            content: "Log into Belgian Company",
            trigger: ".o_menu_systray .o_switch_company_menu",
            run: "click",
        },
        {
            content: "Log into Belgian Company",
            trigger:
                ".o-dropdown--menu .dropdown-item div span:contains('My Belgian Company - TEST')",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: `.oe_topbar_name:contains(My Belgian Company - TEST)`,
        },
        {
            content: "Open Activity Systray",
            trigger: ".o-mail-ActivityMenu-counter",
            run: "click",
        },
        {
            content: "Open Sign Requests",
            trigger: '.o-dropdown--menu .list-group-item:contains("Signature")',
            run: "click",
        },
        {
            content: "Go to Signable Document",
            trigger: "button[name='go_to_signable_document']",
            run: "click",
        },
        {
            content: "Next 1",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Next 2",
            trigger: ":iframe .o_sign_sign_item_navigator",
            run: "click",
        },
        {
            content: "Click Signature",
            trigger: ":iframe button.o_sign_sign_item",
            run: "click",
        },
        {
            content: "Click Auto",
            trigger: "a.o_web_sign_auto_button:contains('Auto')",
            run: "click",
        },
        {
            content: "Adopt & Sign",
            trigger: "footer.modal-footer button.btn-primary:enabled",
            run: "click",
        },
        {
            trigger: ":iframe body:not(:has(footer.modal-footer button.btn-primary))",
        },
        {
            content: "Validate and Sign",
            trigger: ".o_sign_validate_banner button",
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("hr_contract_salary_tour_with_mobility_budget", {
    steps: () => [
        ...salaryConfigTourStart(),
        ...salaryConfigTourPersonalInfo(),
        {
            content: "Take Extra-Legal Leaves",
            trigger: 'input[list="holidays_range"]',
            run: "range 10",
        },
        {
            trigger: 'span[name="Gross"][value="2522.34"]',
        },
        {
            content: "Take Mobility Budget",
            trigger: 'input[name="fold_l10n_be_mobility_budget_amount_monthly"]:not(:visible)',
            run: "click",
        },
        {
            trigger: 'span[name="Gross"][value="2524.11"]',
        },
        {
            trigger: 'span[name="Net"][value="2166"]',
        },
        {
            trigger: 'span[name="Employer Cost"][value="56359.8"]',
        },
        {
            trigger: 'body',
            run: function () {
                var input = this.anchor.querySelector('input[name="l10n_be_mobility_budget_amount_monthly"]');
                if (input.value != '508.19') {
                    throw new Error("Mobility Budget Amount is not correct.");
                }
            },
        },
        ...salaryConfigTourSubmitAndSign()
    ],
});
