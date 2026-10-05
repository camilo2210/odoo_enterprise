import { Component, proxy, t, useProps } from "@odoo/owl";
import { InteractiveEditorSidebar } from "@web_studio/client_action/view_editor/interactive_editor/interactive_editor_sidebar";
import { SidebarViewToolbox } from "@web_studio/client_action/view_editor/interactive_editor/sidebar_view_toolbox/sidebar_view_toolbox";

export class DefaultViewSidebar extends Component {
    static template = "web_studio.ViewEditor.DefaultViewSidebar";
    static components = {
        InteractiveEditorSidebar,
        SidebarViewToolbox,
    };

    props = useProps({
        openViewInForm: t.function().optional(),
        openDefaultValues: t.function().optional(),
    });

    setup() {
        this.viewEditorModel = proxy(this.env.viewEditorModel);
    }
}
