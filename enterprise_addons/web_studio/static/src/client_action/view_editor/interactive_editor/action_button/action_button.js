import { Component, computed, proxy, signal, t, usePlugin, useProps } from "@odoo/owl";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { uniqueId } from "@web/core/utils/functions";
import { StudioHook } from "../../editors/components/studio_hook_component";

export class AddButtonAction extends Component {
    static template = `web_studio.AddButtonAction`;

    onClick(ev) {
        let nextButtonCount = 1;
        const findHeader =
            this.env.viewEditorModel.xmlDoc.firstChild.querySelector(":scope > header");
        if (!findHeader) {
            this.env.viewEditorModel.pushOperation({
                type: "statusbar",
                view_id: this.env.viewEditorModel.view.id,
            });
        } else {
            nextButtonCount = findHeader.querySelectorAll(":scope > button").length + 1;
        }
        this.env.viewEditorModel.doOperation({
            type: "add_header_button",
        });
        this.env.setAutoClick(
            {
                xpath: `/${this.env.viewEditorModel.viewType}[1]/header[1]/button[${nextButtonCount}]`,
            },
            {}
        );
    }
}

export class SelectionHeaderButtons extends Component {
    static template = `web_studio.SelectionHeaderButtons`;
    static components = {
        AddButtonAction,
        StudioHook,
    };

    props = useProps({
        headerButtons: t.array(t.object()),
    });

    hookId = uniqueId("statusbar_button_");
    buttonsContainerRef = signal.ref();

    debugMode = usePlugin(DebugModePlugin);

    buttons = computed(() => {
        if (this.viewEditorModel.showInvisible) {
            return this.props.headerButtons.map((btn) => {
                if (btn.invisible === "True" || btn.invisible === "1") {
                    return {
                        ...btn,
                        className: `${btn.className} o_web_studio_show_invisible`,
                    };
                }
                return btn;
            });
        }
        return this.props.headerButtons.filter(
            (btn) => btn.invisible !== "True" && btn.invisible !== "1"
        );
    });

    setup() {
        this.viewEditorModel = proxy(this.env.viewEditorModel);
        this.viewEditorModel.dropHooks.use({
            id: this.hookId,
            accept: ({ element }) => element.dataset.hookId === this.hookId,
            getHookConfig: ({ targetInfo }) => targetInfo,
            highlightHooks: ({ element, hooks }) => {
                const el = this.buttonsContainerRef();
                el.classList.add("o_web_studio_hook-highlight");
                return () => {
                    el.classList.remove("o_web_studio_hook-highlight");
                };
            },
        });
    }
    makeTooltipButton(button) {
        return JSON.stringify({
            button: {
                string: button.string,
                type: button.clickParams?.type,
                name: button.clickParams?.name,
            },
            debug: true,
        });
    }
    getClassName(button) {
        return button.className.includes("btn-primary")
            ? button.className
            : `btn-secondary ${button.className}`;
    }
}
