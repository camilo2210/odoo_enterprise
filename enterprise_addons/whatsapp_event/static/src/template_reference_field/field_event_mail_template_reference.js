import { patch } from "@web/core/utils/patch";
import { EventMailTemplateReferenceField } from "@event/template_reference_field/field_event_mail_template_reference";

patch(EventMailTemplateReferenceField.prototype, {
    get m2oProps() {
        // Since whatsapp templates need to be approved first, 
        // it doesnt make sense to allow these templates to be 
        // created or edited becuase then they need to be approved/re-approved before use.
        const props = super.m2oProps;
        if (props.relation === "whatsapp.template") {
            props.canCreate = false;
            props.canQuickCreate = false;
            props.canCreateEdit = false;
        }
        return props;
    },
});
