import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";
import { browser } from "@web/core/browser/browser";

const oldWriteText = browser.navigator.clipboard.writeText;

registry.category("web_tour.tours").add('appointment_crm_meeting_tour', {
    steps: () => [stepUtils.showAppsMenuItem(), {
        trigger: '.o_app[data-menu-xmlid="crm.crm_menu_root"]',
        run: 'click',
    },
    {
        trigger: ".o_opportunity_kanban",
    },
    {
        trigger: '.o_kanban_record:contains("Test Opportunity")',
        run: 'click',
    }, {
        trigger: 'button[name="action_schedule_meeting"]',
        run: 'click',
    }, {
        trigger: 'button:contains("Share")',
        run: 'click',
    },
    {
        trigger: 'span:contains("One-time link")',
        async run(helpers) {
            // Patch and ignore write on clipboard in tour as we don't have permissions
            browser.navigator.clipboard.writeText = () => { console.info('Copy in clipboard ignored!') };
            await helpers.click();
        },
    }, {
        trigger: '.o_notification:contains("Link copied to clipboard!")',
        run() {
            // Cleanup the patched clipboard method
            browser.navigator.clipboard.writeText = oldWriteText;
        },
    }],
});
