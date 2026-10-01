import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { redirect } from "@web/core/utils/urls";

registry.category("web_tour.tours").add('appointment_hr_recruitment_tour', {
    steps: () => [stepUtils.showAppsMenuItem(), {
        trigger: '.o_app[data-menu-xmlid="hr_recruitment.menu_hr_recruitment_root"]',
        run: 'click',
    }, {
        trigger: '.o_kanban_record:contains("Test Job")',
        run: 'click',
    }, {
        trigger: '.o_kanban_record:contains("Test Applicant")',
        run: 'click',
    },{
        trigger: 'button[name="action_create_meeting"]',
        run: 'click',
    }, {
        trigger: 'button:contains("Share")',
        run: 'click',
    }, {
        trigger: 'span:contains("My availabilities")',
        async run(helpers) {
            // Patch clipboard write to check the applicant_code is included, then
            // navigate to the url to book an appointment from there.
            // No need to cleanup as it triggers an unload.
            navigator.clipboard.writeText = (text) => {
                if (!text || !text.includes("applicant_code=")) {
                    console.error("All urls should get the applicant_code included.");
                }
                redirect(text);
            };
            await helpers.click();
        },
        expectUnloadPage: true,
    }, {
        trigger: '.o_slot_hours',
        run: 'click',
    }, {
        trigger: "button[name='submitSlotInfoSelected']",
        run: 'click',
        expectUnloadPage: true,
    }, {
        trigger: 'input[name="name"]',
        run: 'edit Ana Tourelle',
    }, {
        trigger: 'input[name="email"]',
        run: 'edit ana@example.com',
    }, {
        trigger: 'input[type="phone"]',
        run: 'edit 3141592',
    }, {
        trigger: '.o_appointment_form_confirm_btn',
        run: 'click',
        expectUnloadPage: true,
    }, {
        trigger: '[data-icon="check_circle"]',
        run: 'click',
    }],
});
