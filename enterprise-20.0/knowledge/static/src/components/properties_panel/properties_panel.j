import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { PropertiesField } from "@web/views/fields/properties/properties_field";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

import { Component, computed, onWillStart, proxy, useOnChange, useProps } from "@odoo/owl";

export class KnowledgeArticleProperties extends Component {
    static template = "knowledge.KnowledgeArticleProperties";
    static components = { PropertiesField };

    props = useProps(standardWidgetProps);

    hasProperties = computed(() =>
        this.props.record.data.article_properties.some((prop) => !prop.definition_deleted)
    );

    setup() {
        this.panelState = proxy(this.env.panelState);
        this.ui = useService("ui");
        // open/close the panel based on the existence of properties
        useOnChange(
            () => [this.hasProperties()],
            () => {
                if (
                    !this.panelState.isSidePanelOpen() &&
                    !this.ui.isSmall &&
                    this.hasProperties() &&
                    !this.panelState.isDisplayed("properties")
                ) {
                    this.panelState.setActivePanel("properties");
                } else if (this.panelState.isDisplayed("properties") && !this.hasProperties()) {
                    this.panelState.setActivePanel();
                }
            }
        );
        onWillStart(async () => (this.userIsInternal = await user.hasGroup("base.group_user")));
    }
}
