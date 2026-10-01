import { Component, useProps, signal, t, useEffect, usePlugin } from "@odoo/owl";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { DomainSelectorDialog } from "@web/core/domain_selector_dialog/domain_selector_dialog";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { useService } from "@web/core/utils/hooks";
import { StudioIconSelector } from "@web_studio/client_action/components/icon_selector/icon_selector";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class Property extends Component {
    static template = "web_studio.Property";
    static components = { CheckBox, SelectMenu, DomainSelectorDialog, StudioIconSelector };
    props = useProps({
        name: t.string(),
        type: t.string(),
        value: t.any().optional(),
        onChange: t.function().optional(),
        childProps: t.object().optional({}),
        class: t.string().optional(""),
        isReadonly: t.boolean().optional(),
        tooltip: t.string().optional(),
        inputAttributes: t.object().optional(),
        autofocus: t.boolean().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);
    rootRef = signal.ref(HTMLDivElement);

    setup() {
        this.dialog = useService("dialog");

        useEffect(() => {
            const el = this.rootRef();
            if (!this.props.autofocus || !el) {
                return;
            }
            void this.env.viewEditorModel.activeNodeXpath; // subscribe: refocus when the active node changes
            if (this.props.type === "selection") {
                el.querySelector(".o_select_menu_toggler").click();
            } else {
                el.querySelector("input")?.focus();
            }
        });
    }

    get className() {
        const propsClass = this.props.class ? this.props.class : "";
        return `o_web_studio_property_${this.props.name} ${propsClass}`;
    }

    onDomainClicked() {
        this.dialog.add(DomainSelectorDialog, {
            resModel: this.props.childProps.relation,
            domain: this.props.value || "[]",
            isDebugMode: this.debugMode.isActive(),
            onConfirm: (domain) => this.props.onChange(domain, this.props.name),
        });
    }

    onViewOptionChange(value) {
        this.props.onChange(value, this.props.name);
    }
}
