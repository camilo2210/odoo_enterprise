import { proxy } from "@odoo/owl";
import { useLayoutEffect, useSubEnv } from "@web/owl2/utils";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";

export class WhatsappComposerFormController extends FormController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.placeholders = proxy({ values: {} });

        // Provide placeholders to child components/widgets
        useSubEnv({ placeholders: this.placeholders });

        // Fetch and update demo placeholder values when the template changes
        useLayoutEffect(
            () => {
                const waTemplateId = this.model.root?.data?.wa_template_id?.id;
                if (!waTemplateId) {
                    this.placeholders.values = {};
                    return;
                }

                const updatePlaceholders = async () => {
                    const templateDemoValues = await this.orm.call(
                        "whatsapp.template",
                        "get_template_demo_values",
                        [waTemplateId]
                    );
                    // Demo values returned by backend are used as placeholder text in the WhatsApp composer
                    this.placeholders.values = { ...templateDemoValues };
                };

                updatePlaceholders();
            },
            () => [this.model.root?.data?.wa_template_id?.id]
        );
    }
}

export const whatsappComposerFormView = {
    ...formView,
    Controller: WhatsappComposerFormController,
};

registry.category("views").add("whatsapp_composer_form", whatsappComposerFormView);
