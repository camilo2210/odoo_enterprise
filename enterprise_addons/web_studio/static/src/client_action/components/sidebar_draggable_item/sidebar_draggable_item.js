import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class SidebarDraggableItem extends Component {
    static template = "web_studio.SidebarDraggableItem";
    props = useProps({
        className: t.string().optional(),
        description: t.string().optional(),
        dropData: t.any().optional(),
        string: t.string(),
        structure: t.string(),
    });

    debugMode = usePlugin(DebugModePlugin);
}
