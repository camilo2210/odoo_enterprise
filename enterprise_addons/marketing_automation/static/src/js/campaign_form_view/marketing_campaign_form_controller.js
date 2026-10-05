import { FormController } from "@web/views/form/form_controller";
import { useSubEnv } from "@odoo/owl";

export class CampaignFormController extends FormController {
    static template = "marketing_automation.CampaignFormView";
    setup() {
        super.setup();
        this.panelState = {};
        useSubEnv({
            panelState: this.panelState,
        });
    }
}
