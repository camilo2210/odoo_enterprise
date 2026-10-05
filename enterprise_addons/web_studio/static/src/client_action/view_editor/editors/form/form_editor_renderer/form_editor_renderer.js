import { onMounted, proxy, signal, t, useEffect, useProps } from "@odoo/owl";
import { settingProps } from "@web/views/form/setting/setting";
import { formView } from "@web/views/form/form_view";
import * as formEditorRendererComponents from "@web_studio/client_action/view_editor/editors/form/form_editor_renderer/form_editor_renderer_components";

import { ChatterContainer, ChatterContainerHook } from "../chatter_container";
import { StudioHook } from "@web_studio/client_action/view_editor/editors/components/studio_hook_component";
import { FieldStudio } from "@web_studio/client_action/view_editor/editors/components/field_studio";
import { WidgetStudio } from "@web_studio/client_action/view_editor/editors/components/widget_studio";
import { ViewButtonStudio } from "@web_studio/client_action/view_editor/editors/components/view_button_studio";
import { InnerGroup, OuterGroup } from "./form_editor_groups";
import { AddButtonAction } from "@web_studio/client_action/view_editor/interactive_editor/action_button/action_button";

class Setting extends formView.Renderer.components.Setting {
    props = useProps({
        ...settingProps,
        studioXpath: t.string().optional(),
        studioIsVisible: t.boolean().optional(),
    });
}
export class FormEditorRenderer extends formView.Renderer {
    static components = {
        ...formView.Renderer.components,
        ...formEditorRendererComponents,
        Field: FieldStudio,
        Widget: WidgetStudio,
        ViewButton: ViewButtonStudio,
        ChatterContainerHook,
        InnerGroup,
        OuterGroup,
        StudioHook,
        Setting,
        AddButtonAction,
    };
    setup() {
        super.setup();
        this.rootRef = signal.ref();
        const viewEditorModel = this.env.viewEditorModel;
        this.viewEditorModel = proxy(viewEditorModel);
        this.mailComponents.Chatter = ChatterContainer;

        useEffect(() => {
            const rootEl = this.rootRef();
            if (!rootEl) {
                return;
            }
            rootEl.classList.add("o_web_studio_form_view_editor");
            if (this.viewEditorModel.showInvisible) {
                rootEl
                    .querySelectorAll(":not(.o-mail-Form-chatter) .o_invisible_modifier")
                    .forEach((el) => {
                        el.classList.add("o_web_studio_show_invisible");
                        el.classList.remove("o_invisible_modifier");
                    });
            } else {
                rootEl
                    .querySelectorAll(":not(.o-mail-Form-chatter) .o_web_studio_show_invisible")
                    .forEach((el) => {
                        el.classList.remove("o_web_studio_show_invisible");
                        el.classList.add("o_invisible_modifier");
                    });
            }
        });

        onMounted(() => {
            const rootEl = this.rootRef();
            if (rootEl) {
                const optCols = rootEl.querySelectorAll("i.o_optional_columns_dropdown_toggle");
                for (const col of optCols) {
                    col.classList.add("text-muted");
                }
            }
        });
    }
}
