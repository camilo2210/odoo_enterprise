import { CrmBusinessCardScanner } from "../../crm_business_card_scanner";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import {
    LeadGenerationDropdown,
    MODULE_STATUS
} from "@crm/components/lead_generation_dropdown/lead_generation_dropdown";
import { _t } from "@web/core/l10n/translation";

patch(LeadGenerationDropdown.prototype, {
    setup() {
        super.setup();
        this.isMobileOS = isMobileOS();
        const appointmentElement = this.state.dropdownContentElements.find(
            element => element.moduleXmlId === 'base.module_appointment'
        );
        const businessCardElement = this.state.dropdownContentElements.find(
            element => element.moduleXmlId === 'base.module_crm_enterprise'
        )
        if (appointmentElement && businessCardElement) return;
        this.state.dropdownContentElements = [
            ...this.state.dropdownContentElements,
            ...(!appointmentElement ? [{
                description: _t("Get leads when people schedule time with you"),
                hasAccess: user.isAdmin,
                icon: "/crm_enterprise/static/img/appointments.png",
                moduleName: "appointment",
                moduleXmlId: "base.module_appointment",
                sequence: 35,
                status: MODULE_STATUS.NOT_INSTALLED,
                title: _t("Appointments"),
            }] : []),
            ...(!businessCardElement ? [{
                description: _t("Create leads from business card pictures"),
                hasAccess: true,
                icon: "/crm_enterprise/static/img/industry_photography.png",
                moduleName: "crm_enterprise",
                moduleXmlId: "base.module_crm_enterprise",
                sequence: 55,
                status: MODULE_STATUS.INSTALLED,
                title: _t("Import business cards"),
                onClick: () => this.scanBusinessCard(),
            }] : [])
        ]
    },

    scanBusinessCard() {
        const businessCardScanner = document.querySelector('.o_crm_business_card_scanner input[type="file"]');
        if (businessCardScanner) {
            businessCardScanner.dispatchEvent(new MouseEvent('click'));
        }
    }
});

LeadGenerationDropdown.components = {
    ...LeadGenerationDropdown.components,
    CrmBusinessCardScanner,
};
