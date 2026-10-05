import { patch } from "@web/core/utils/patch";
import {
    LeadGenerationDropdown,
    MODULE_STATUS
} from "@crm/components/lead_generation_dropdown/lead_generation_dropdown";

patch(LeadGenerationDropdown.prototype, {
    setup() {
        super.setup();
        const appointmentElement = this.state.dropdownContentElements.find(element => element.moduleXmlId === 'base.module_appointment');
        Object.assign(appointmentElement, {
            onClick: () => this.createAppointment(),
            status: MODULE_STATUS.INSTALLED,
            model: 'appointment.type',
        });
    },
    async createAppointment() {
        const action = await this.orm.call(
            'appointment.type',
            'action_setup_appointment_type_template',
            ['meeting', { "lead_create": true }],
        );
        await this.action.doAction(action);
    }
});
