import { Component, xml, proxy, t, useProps } from "@odoo/owl";
import { SidebarPropertiesToolbox } from "@web_studio/client_action/view_editor/interactive_editor/properties/sidebar_properties_toolbox/sidebar_properties_toolbox";

class DefaultProperties extends Component {
    static template = xml`
        <SidebarPropertiesToolbox/>
    `;
    static components = { SidebarPropertiesToolbox };
    props = useProps({
        node: t.object(),
    });
}

export class Properties extends Component {
    static template = "web_studio.ViewEditor.InteractiveEditorProperties";
    static components = { DefaultProperties };
    props = useProps({
        propertiesComponents: t.object(),
    });

    setup() {
        this.viewEditorModel = proxy(this.env.viewEditorModel);
    }

    get iconClass() {
        // first check if the structure has a dedicated icon
        let icon =
            this.env.viewEditorModel.editorInfo.editor.Sidebar.viewStructures?.[this.nodeType]
                ?.class;
        if (!icon && this.nodeType === "field") {
            icon = `o_web_studio_field_${this.node.field.type}`;
        }
        return icon || `o_web_studio_field_${this.nodeType}`;
    }

    get node() {
        return this.viewEditorModel.activeNode;
    }

    get propertiesComponent() {
        return this.props.propertiesComponents[this.nodeType] || {};
    }

    get nodeType() {
        return this.node?.arch.tagName;
    }
}
