import {
    Component,
    computed,
    onMounted,
    onWillUnmount,
    Plugin,
    Resource,
    types as t,
    useConfig,
    usePlugin,
    useProps,
    xml,
} from "@odoo/owl";
import { Notebook } from "@web/core/notebook/notebook";
import { ResizablePanel } from "@web/core/resizable_panel/resizable_panel";
import { SaveDiscard } from "./report_editor_components";

class ComponentList extends Component {
    static template = xml`
        <t t-foreach="this.props.components" t-as="item" t-key="item.name + item_index" t-component="item"/>
    `;
    props = useProps({ components: t.array() });
}

class ReportNotebook extends Notebook {
    static template = "web_studio.ReportEditor.Notebook";
}

export class ReportEditorSidebar extends Component {
    static template = "web_studio.ReportEditorSidebar";
    static components = { ResizablePanel, ReportNotebook };

    sidebarPlugin = usePlugin(ReportEditorSidebarPlugin);
    pages = computed(() =>
        this.sidebarPlugin.pages.map((page) => ({
            Component: ComponentList,
            props: { components: page.components },
            title: page.title,
            name: page.name,
            mode: page.mode,
        }))
    );
    icons = computed(() =>
        Object.fromEntries(this.sidebarPlugin.pages.map((page, i) => [i, page.icon]))
    );

    startItems = computed(() =>
        this.sidebarPlugin.components.items().filter((i) => i.position === "start")
    );
    endItems = computed(() =>
        this.sidebarPlugin.components.items().filter((i) => i.position === "end")
    );

    async setMode(mode) {
        if (this.env.reportEditorModel.mode !== mode) {
            await this.sidebarPlugin._saveFn?.();
            this.env.reportEditorModel.mode = mode;
        }
    }
}

export class ReportEditorSidebarPlugin extends Plugin {
    pages = useConfig("pages", t.array());
    components = new Resource({ name: "components" });

    _nextId = 0;
    _saveFn = null;

    addComponent(component, position, props = {}) {
        const item = { component, position, props, id: this._nextId++ };
        onMounted(() => this.components.add(item));
        onWillUnmount(() => this.components.delete(item));
    }

    useSave({ isDirty, save, discard }) {
        this.addComponent(SaveDiscard, "start", { isDirty, save, discard });
        onMounted(() => (this._saveFn = save));
        onWillUnmount(() => {
            if (this._saveFn == save) {
                this._saveFn = null;
            }
        });
    }
}
