import { Component, computed, proxy, Resource, signal, t, useEffect, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { uniqueId } from "@web/core/utils/functions";
import { useOwnedDialogs } from "@web/core/utils/hooks";
import { formView } from "@web/views/form/form_view";
import { FieldSelectorDialog } from "@web_studio/client_action/view_editor/editors/components/field_selector_dialog";
import { StudioHook } from "@web_studio/client_action/view_editor/editors/components/studio_hook_component";
import {
    randomName,
    studioIsVisible,
    useStudioRef,
} from "@web_studio/client_action/view_editor/editors/utils";
import { NewButtonBoxDialog } from "@web_studio/client_action/view_editor/interactive_editor/properties/button_properties/new_button_box_dialog";
import { AddButtonAction } from "../../../interactive_editor/action_button/action_button";

/**
 * Overrides and extensions of components used by the FormRenderer
 * As a rule of thumb, elements should be able to handle the props
 * - studioXpath: the xpath to the node in the form's arch to which the component
 *   refers
 * - They generally be clicked on to change their characteristics (in the Sidebar)
 * - The click doesn't trigger default behavior (the view is inert)
 * - They can be draggable (FormLabel referring to a field)
 * - studioIsVisible: all components whether invisible or not, are compiled and rendered
 *   this props allows to toggle the class o_invisible_modifier
 * - They can have studio hooks, that are placeholders for dropping content (new elements, field, or displace elements)
 */

const components = formView.Renderer.components;

/*
 * FormLabel:
 * - Can be draggable if in InnerGroup
 */
export class FormLabel extends components.FormLabel {
    static template = "web_studio.FormLabel";

    studioProps = useProps({
        studioXpath: t.string(),
        studioIsVisible: t.boolean().optional(),
    });

    setup() {
        super.setup();
        this.rootRef = useStudioRef(this.onClick.bind(this));
    }
    get className() {
        let className = super.className;
        if (!studioIsVisible(this.studioProps)) {
            className += " o_web_studio_show_invisible";
        }
        className += " o-web-studio-editor--element-clickable";
        return className;
    }
    onClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.env.config.onNodeClicked(this.studioProps.studioXpath);
    }
}

/*
 * Notebook:
 * - Display every page, the elements in the page handle whether they are invisible themselves
 * - Push a droppable hook on every empty page
 * - Can add a new page
 */
export class Notebook extends components.Notebook {
    static template = "web_studio.Notebook.Hook";
    static components = { ...components.Notebook.components, StudioHook };

    studioProps = useProps({
        studioIsVisible: t.boolean().optional(),
        studioXpath: t.string(),
    });

    static __id = 0;
    rootRef = signal.ref();
    hooksRef = new Resource();

    draggableElements = computed(() => {
        void this.env.viewEditorModel.showInvisible;
        return this.rootRef()?.querySelectorAll(":scope > li.nav-item button") || [];
    });

    componentId = ++this.constructor.__id;
    hookId = "notebook_" + this.componentId;

    setup() {
        this.viewEditorModel = proxy(this.env.viewEditorModel);
        super.setup();

        useEffect(() => {
            const hooks = this.hooksRef.items();
            let i = 0;
            while (i < hooks.length) {
                hooks[i].classList.remove("d-none");
                if (hooks[i].nextElementSibling === hooks[i + 1]) {
                    hooks[i + 1].classList.add("d-none");
                    i++;
                }
                i++;
            }
        });

        useEffect(() => {
            const currentPage = this.getCurrentPage();
            for (const draggable of this.draggableElements()) {
                if (draggable.classList.contains("o_web_studio_add_form_page")) {
                    continue;
                }
                draggable.dataset.hookId = this.hookId;

                if (draggable.classList.contains("o-draggable")) {
                    draggable.classList.remove("o-draggable");
                }
                if (currentPage[1].studioXpath === draggable.dataset.studioXpath) {
                    draggable.classList.add("o-draggable");
                }
            }
        });
        this.env.viewEditorModel.dropHooks.use({
            id: this.hookId,
            accept: ({ element }) => element.dataset.hookId === this.hookId,
            getHookConfig: ({ targetInfo }) => targetInfo,
            highlightHooks: ({ element, hooks }) => {
                const el = this.rootRef();
                el.classList.add("o_web_studio_hook-highlight");
                return () => {
                    el.classList.remove("o_web_studio_hook-highlight");
                };
            },
        });
    }

    getCurrentPage = computed(() =>
        this.pages().find((page) => page[0] === this.state.currentPage)
    );

    computePages(props) {
        const pages = super.computePages(props);
        pages.forEach((p) => {
            p[1].studioIsVisible = p[1].isVisible;
            p[1].isVisible = p[1].isVisible || this.viewEditorModel.showInvisible;
        });
        return pages;
    }

    studioOnPageClicked(ev, navItem) {
        this.activatePage(navItem[0]);
        this.env.config.onNodeClicked(navItem[1].studioXpath, ev.detail);
    }

    onNewPageClicked() {
        const vem = this.viewEditorModel;
        const node = {
            tag: "page",
            attrs: {
                string: _t("New Page"),
                name: randomName("studio_page"),
            },
        };
        vem.doOperation({
            type: "add",
            node,
            target: vem.getFullTarget(this.studioProps.studioXpath),
            position: "inside",
        });
    }

    _getNavItemClasses(navItem) {
        const classes = super._getNavItemClasses(navItem);
        classes["o-web-studio-editor--element-clickable"] = true;
        return classes;
    }
}

export class StatusBarButtons extends components.StatusBarButtons {
    static template = `web_studio.FormViewAddButtonAction`;
    static components = {
        ...components.StatusBarButtons.components,
        AddButtonAction,
    };

    hooksRef = new Resource();
    rootRef = signal.ref();
    draggableElements = computed(() => {
        void this.env.viewEditorModel.showInvisible;
        return this.rootRef()?.querySelectorAll(":scope > *[name][studioxpath]") || [];
    });

    hookId = uniqueId("statusbar_button_");

    setup() {
        super.setup();
        useEffect(() => {
            const hooks = this.hooksRef.items();
            let i = 0;
            while (i < hooks.length) {
                hooks[i].classList.remove("d-none");
                if (hooks[i].nextElementSibling === hooks[i + 1]) {
                    hooks[i + 1].classList.add("d-none");
                    i++;
                }
                i++;
            }
        });

        useEffect(() => {
            for (const draggable of this.draggableElements()) {
                draggable.classList.add("o-draggable");
                draggable.dataset.structure = "statusBarButton";
                draggable.dataset.hookId = this.hookId;
            }
        });
        this.env.viewEditorModel.dropHooks.use({
            id: this.hookId,
            accept: ({ element }) => element.dataset.hookId === this.hookId,
            getHookConfig: ({ targetInfo }) => targetInfo,
            highlightHooks: ({ element, hooks }) => {
                const el = this.rootRef();
                el.classList.add("o_web_studio_hook-highlight");
                return () => {
                    el.classList.remove("o_web_studio_hook-highlight");
                };
            },
        });
    }
}

export class StatusBarFieldHook extends Component {
    static template = "web_studio.StatusBarFieldHook";

    props = useProps({
        addStatusBar: t.boolean(),
    });

    hookRef = signal.ref();
    setup() {
        this.addDialog = useOwnedDialogs();
        this.hookId = "form_statusbar";
        const vem = this.env.viewEditorModel;

        this.dropHook = {
            id: this.hookId,
            accept: ({ element }) => {
                if (element.dataset.structure === "field") {
                    const dropData = JSON.parse(element.dataset.drop);
                    if (["many2one", "selection"].includes(dropData.fieldType)) {
                        return true;
                    } else if ("fieldName" in dropData) {
                        const field = vem.fields[dropData.fieldName];
                        return ["many2one", "selection"].includes(field.type);
                    }
                }
                return false;
            },
            getHookConfig: ({ config }) => {
                const targetXpath = "/form[1]/header[1]";
                const target = {
                    tag: "header",
                    xpath: targetXpath,
                    xpath_info: [
                        {
                            tag: "form",
                            indice: 1,
                        },
                        {
                            tag: "header",
                            indice: 1,
                        },
                    ],
                };
                const subViewXpath = vem.getSubviewXpath();
                if (subViewXpath) {
                    target.subview_xpath = subViewXpath;
                }
                return {
                    ...config,
                    target,
                    xpath: targetXpath,
                    position: "inside",
                    getOperations: ({ operation }) => {
                        if (operation.node.field_description?.type === "selection") {
                            operation.node.field_description.default_value = true;
                        }

                        Object.assign(operation.node.attrs, {
                            widget: "statusbar",
                            options: "{'clickable': '1'}",
                        });
                        return this.props.addStatusBar
                            ? [{ type: "statusbar" }, operation]
                            : [operation];
                    },
                };
            },
        };
        vem.dropHooks.use(this.dropHook);
    }
    get classNames() {
        return "o_web_studio_statusbar_hook o_web_studio_hook_special";
    }
    get title() {
        return _t("Add a pipeline status bar");
    }
}

export class AvatarHook extends Component {
    static template = "web_studio.AddElementHook";

    props = useProps({
        fields: t.object(),
    });

    hookRef = signal.ref();
    setup() {
        this.addDialog = useOwnedDialogs();
    }
    get classNames() {
        return "oe_avatar ms-3 o_web_studio_avatar";
    }
    get title() {
        return _t("Add Picture");
    }
    onClick() {
        const fields = [];
        for (const field of Object.values(this.props.fields)) {
            if (field.type === "binary") {
                fields.push(field);
            }
        }
        this.addDialog(FieldSelectorDialog, {
            fields,
            showNew: true,
            onConfirm: (field) => {
                this.env.viewEditorModel.doOperation({
                    type: "avatar_image",
                    field,
                });
            },
        });
    }
}

export class ButtonHook extends Component {
    static template = "web_studio.AddSmartButton";

    props = useProps({
        add_buttonbox: t.boolean().optional(),
        studioIsVisible: t.boolean().optional(),
    });

    setup() {
        this.addDialog = useOwnedDialogs();
    }
    get classNames() {
        return "oe_stat_button o_web_studio_button_hook flex-grow-1 flex-lg-grow-0";
    }
    onClick() {
        this.addDialog(NewButtonBoxDialog, {
            model: this.env.viewEditorModel,
            isAddingButtonBox: Boolean(this.props.add_buttonbox),
        });
    }
}

export class ButtonBox extends components.ButtonBox {
    static template = "web_studio.ButtonBox";
    static components = { StudioHook, ButtonHook };

    studioProps = useProps({
        addButtonBox: t.boolean().optional(false),
        studioIsVisible: t.boolean().optional(),
    });
    togglerRef = signal.ref();

    rootRef = signal.ref();
    buttonContainers = new Resource();
    draggableElements = computed(() => {
        void this.env.viewEditorModel.showInvisible;
        return this.buttonContainers
            .items()
            .flatMap((el) => [...el.querySelectorAll(":scope > *[name][studioxpath]")]);
    });
    hookId = uniqueId("button_box_");
    setup() {
        super.setup();
        this.viewEditorModel = this.env.viewEditorModel;
        this.expanded = proxy({ value: false });
        this.viewEditorModel.dropHooks.use({
            id: this.hookId,
            accept: ({ element }) => element.dataset.hookId === this.hookId,
            getHookConfig: ({ targetInfo }) => targetInfo,
            highlightHooks: ({ element, hooks }) => {
                const el = this.rootRef();
                el.classList.add("o_web_studio_hook-highlight");
                return () => {
                    el.classList.remove("o_web_studio_hook-highlight");
                };
            },
        });

        useEffect(() => {
            for (const draggable of this.draggableElements()) {
                draggable.classList.add("o-draggable");
                draggable.dataset.structure = "buttonBox";
                draggable.dataset.hookId = this.hookId;
            }
        });
    }

    toggle() {
        this.expanded.value = !this.expanded.value;
        this.togglerRef().classList.toggle("show", this.expanded.value);
        this.togglerRef().ariaExpanded = this.expanded.value;
    }

    getSlotInfo(slot) {
        return this.props.slots[slot];
    }

    isSlotVisible(slot) {
        if (slot.studio_fake_slot) {
            return false;
        }
        if (this.viewEditorModel.isEditingSubview) {
            return false;
        }
        return this.viewEditorModel.showInvisible || super.isSlotVisible(slot);
    }
}
