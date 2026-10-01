import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("whatsapp_partner_tour", {
    steps: () => [
        ...stepUtils.goToAppSteps("contacts.menu_contacts", "Open the contacts menu"),
        {
            trigger: ".o_data_cell:contains('32499123456')",
            content: "Open the form view of partner 32499123456",
            run: "click",
        },
        stepUtils.autoExpandMoreButtons(),
        {
            trigger:
                "button[name='action_open_partner_wa_channels'] div[name='wa_channel_count']:contains(1)",
            content: "Click on the WhatsApp Chats button",
            run: "click",
        },
        {
            trigger: ".o_data_cell:contains('32499123456')",
            run: "click",
            content: "Open chat in chatwindow",
        },
        { trigger: ".o-mail-Message-content:contains('Testing message from 32499123456')" },
    ],
});
