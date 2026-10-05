import { Component, proxy } from "@odoo/owl";
import { LimitGroupVisibility } from "@web_studio/client_action/view_editor/interactive_editor/properties/limit_group_visibility/limit_group_visibility";
import { SidebarPropertiesToolbox } from "@web_studio/client_action/view_editor/interactive_editor/properties/sidebar_properties_toolbox/sidebar_properties_toolbox";

export class ViewStructureProperties extends Component {
    static components = { LimitGroupVisibility, SidebarPropertiesToolbox };
    static template = "web_studio.ViewStructureProperties";

    setup() {
        this.viewEditorModel = proxy(this.env.viewEditorModel);
    }
}
