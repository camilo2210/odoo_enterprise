import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

registry.category("web_tour.tours").add("appointment_crm_forced_staff_user_tour", {
    steps: () => [
    {
        content: "Select an appointment.",
        trigger: `a[title='Book Resource Time Appointment']`,
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Select a time slot.",
        trigger: "button[name='submitSlotInfoSelected']",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Fill the full name field in the appointment form.",
        trigger: "input[name='name']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "Customer Name";
            }
        },
    },
    {
        content: "Fill the email field in the appointment form.",
        trigger: "input[name='email']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "customer@odoo.com";
            }
        },
    },
    {
        content: "Fill the phone number field in the appointment form.",
        trigger: "input[type='phone']",
        run: function () {
            if (!this.anchor.value){
                this.anchor.value = "+1 555-555-5555";
            }
        },
    },
    {
        content: "Submit the appointment form.",
        trigger: ".o_appointment_form_confirm_btn",
        run: "click",
        expectUnloadPage: true,
    },
    stepUtils.goToUrl("/appointment"),
    {
        content: "Select an appointment.",
        trigger: `a[title='Book Create']`,
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Verify presence the forced staff user alert with the correct salesperson.",
        trigger: ".o_appointment_forced_staff_user_assigned:contains('Laetitia Sales Leads')",
    },
    {
        content: "Select a time slot.",
        trigger: "button[name='submitSlotInfoSelected']",
        run: "click",
        expectUnloadPage: true,
    },
    {
        content: "Submit the appointment form.",
        trigger: ".o_appointment_form_confirm_btn",
        run: "click",
        expectUnloadPage: true,
    },
]});
