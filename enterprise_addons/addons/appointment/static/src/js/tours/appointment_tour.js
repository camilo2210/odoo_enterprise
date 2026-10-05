import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

import { markup } from "@odoo/owl";

registry.category("web_tour.tours").add("appointment_tour", {
    steps: () => [
        stepUtils.showAppsMenuItem(),
        {
            trigger: ".o_app[data-menu-xmlid='appointment.main_menu_appointments']",
            content: markup(_t("Let's start by opening the <b>Appointments</b> app.")),
            run: "click",
        },
        {
            trigger: ".o_appointment_kanban .o_kanban_renderer",
        },
        {
            trigger: ".o-kanban-button-new",
            content: markup(_t("<b>Create your first appointment.</b>")),
            run: "click",
        },
        {
            trigger: ".modal .o_appointment_template_card:first",
            content: markup(
                _t("Let's start with a simple way to let people <b>book time with you.</b>")
            ),
            run: "click",
        },
        {
            trigger: ".o_field_widget[name='appointment_duration'] > .o_input",
            content: _t("Decide how long the meeting should last."),
            run: "click",
        },
        {
            trigger: ".o_statusbar_buttons > button[name='action_share_invite']",
            content: markup(
                _t("Share your booking link so anyone can <b>schedule a meeting with you.</b>")
            ),
            run: "click",
        },
        {
            trigger: ".o_appointment_invite_copy_save",
            run: "allowClipboardWrite",
        },
        {
            content: _t("Copy the link to your clipboard."),
            trigger: ".o_appointment_invite_copy_save",
            run: "click",
        },
        {
            trigger: ".o_notification:contains('Link copied to clipboard!')",
        },
        {
            trigger: "body:not(:has(.modal))",
        },
        {
            isActive: ["mobile"],
            trigger: ".o_control_panel_main button.o_button_more",
            content: _t("Open action menu."),
            run: "click",
        },
        {
            trigger: ".oe_stat_button[name='action_calendar_meetings']",
            run: "restoreClipboardWrite",
        },
        {
            trigger: ".oe_stat_button[name='action_calendar_meetings']",
            content: markup(
                _t("Want to create one yourself? <b>Open your schedule</b> to create an appointment.")
            ),
            run: "click",
        },
        {
            trigger: ".o_gantt_button_add, .o_gantt_cell",
            content: _t("Click anywhere to create a meeting yourself."),
            run: "click",
        },
        {
            trigger: "div[name='name'] input",
            content: _t("Give your meeting a title."),
            run: "edit Meeting",
        },
        {
            trigger: "div[name='partner_ids'] input",
            content: _t(
                "Enter the name of someone you would like to invite to your first meeting."
            ),
            run: "edit a",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:not(:has(.o_loading))",
            content: _t("Select this attendee."),
            run: "click",
        },
        {
            isActive: ["mobile"],
            trigger: ".o_select_create_dialog_content button.o_form_button_cancel",
            content: _t("Go back to the previous screen."),
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            content: _t("Click Save!"),
            run: "click",
        },
        {
            trigger: ".o_gantt_button_today",
            content: _t("Focus on today to see your new meeting."),
            run: "click",
        },
        {
            trigger: ".o_gantt_pill",
            content: _t(
                "Click on the appointment in your schedule to get an overview of its details."
            ),
            run: "click",
        },
        {
            trigger: ".o_gantt_popover [data-icon='close']",
            content: _t("Close the appointment overview to continue."),
            run: "click",
        },
        {
            isActive: ["mobile"],
            trigger: "nav .o_menu_toggle",
            content: _t("Open menu and select the Appointments."),
            run: "click",
        },
        {
            isActive: ["mobile"],
            trigger: "li[data-menu-xmlid='appointment.appointment_type_menu']",
            content: _t("Go back to the Appointments home screen."),
            run: "click",
        },
        {
            isActive: ["desktop"],
            trigger: ".o-dropdown-item[data-menu-xmlid='appointment.appointment_type_menu']",
            content: _t("Go back to the Appointments home screen."),
            run: "click",
        },
        {
            trigger: ".o_appointment_kanban .o_kanban_renderer",
        },
        {
            trigger: ".o_appointment_kanban_card span:contains('upcoming')",
            content: markup(
                _t("Use <b>Upcoming Meetings</b> to jump straight back into your schedule at the date of the next meeting.")
            ),
            run: "click",
        },
    ],
});
