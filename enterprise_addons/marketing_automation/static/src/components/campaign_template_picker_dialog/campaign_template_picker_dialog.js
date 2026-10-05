import { Component, onWillStart, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";

class CampaignTemplatePickerSheet extends Component {
    static template = "marketing_automation.CampaignTemplatePickerDialogSheet";
    props = useProps({
        activeTemplate: t.object(),
        setActive: t.function(),
        templates: t.object(),
        title: t.string(),
    });
}

/**
 * This component will display a campaign template picker.
 * User will be able to select a template
 */
export class CampaignTemplatePickerDialog extends Component {
    static template = "marketing_automation.CampaignTemplatePickerDialog";
    static components = {
        Dialog,
        CampaignTemplatePickerSheet,
    };
    props = useProps({ close: t.function().optional() });
    /**
     * @override
     */
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.activeTemplate = proxy({});

        this.notebookPages = [];

        onWillStart(async () => {
            // Fetch campaign template data, in a set of template groups containing a set of templates
            const templateGroups = await this.orm.call(
                "marketing.campaign",
                "get_campaign_templates_info",
                []
            );

            // Set default active template to the first template in the first group
            const firstGroup = Object.keys(templateGroups)[0];
            this.setActive(Object.keys(templateGroups[firstGroup].templates)[0]);

            // Use templateGroups set to populate the pages used by the notebook
            for (const [groupId, groupValues] of Object.entries(templateGroups)) {
                this.notebookPages.push({
                    Component: CampaignTemplatePickerSheet,
                    id: groupId,
                    props: {
                        activeTemplate: this.activeTemplate,
                        setActive: (arg) => this.setActive(arg),
                        templates: groupValues.templates,
                    },
                    title: groupValues.label,
                });
            }
        });
    }

    /**
     * On template selection, use active template name to perform an action generating the template
     */
    async onLoadTemplate() {
        const action = await this.orm.call(
            "marketing.campaign",
            "get_action_marketing_campaign_from_template",
            [this.activeTemplate.name]
        );
        if (!action) {
            return;
        }
        this.action.doAction(action, {
            stackPosition: "replaceCurrentAction",
        });
        this.props.close();
    }

    /**
     * Set active template
     */
    setActive(templateName) {
        this.activeTemplate.name = templateName;
    }
}
