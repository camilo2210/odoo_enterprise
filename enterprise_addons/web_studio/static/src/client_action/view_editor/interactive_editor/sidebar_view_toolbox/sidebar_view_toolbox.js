import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class SidebarViewToolbox extends Component {
    static template = "web_studio.ViewEditor.ViewToolbox";
    props = useProps({
        canEditXml: t.boolean().optional(),
        onMore: t.function().optional(),
        openDefaultValues: t.function().optional(),
        canEditDefaultValues: t.boolean().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);
}
