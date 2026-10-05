import {
    Component,
    onError,
    onMounted,
    onPatched,
    signal,
    t,
    toRaw,
    useProps,
    xml,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useSubEnv } from "@web/owl2/utils";
import { WithSearch } from "@web/search/with_search/with_search";
import { cleanClickedElements } from "@web_studio/client_action/view_editor/editors/utils";

export class StudioView extends Component {
    static components = { WithSearch };
    static template = xml`
        <div class="w-100 h-100" t-att-class="{ 'pe-none': this.studioViewProps.setOverlay }" t-ref="this.viewRendererRef">
            <WithSearch t-props="this.props" t-slot-scope="searchParams">
                <t
                    t-component="this.viewEditorModel.editorInfo.editor.Controller"
                    t-props="{ ...this.viewEditorModel.controllerProps, ...searchParams }"
                />
            </WithSearch>
        </div>
    `;

    /** Same as {@link "@web/views/view"}: this is just a wrapper */
    props = useProps();
    studioViewProps = useProps({
        autoClick: t.function().optional(),
        setOverlay: t.boolean().optional(),
    });

    viewRendererRef = signal.ref();

    setup() {
        this.notification = useService("notification");
        this.viewEditorModel = this.env.viewEditorModel;

        if (this.viewEditorModel.initialState.activeNodeXpath) {
            onMounted(() => {
                const initialActiveNodeXpath = this.viewEditorModel.initialState.activeNodeXpath;
                this.viewEditorModel.initialState.activeNodeXpath = null;
                this.viewEditorModel.activeNodeXpath = initialActiveNodeXpath;
            });
        }
        let lastActiveNodeXpath;
        const applyActiveNode = () => {
            const xpath = this.viewEditorModel.activeNodeXpath;
            if (xpath === lastActiveNodeXpath) {
                return;
            }
            lastActiveNodeXpath = xpath;
            if (xpath) {
                this.updateActiveNode({ xpath, resetSidebarOnNotFound: true });
            }
        };
        onMounted(applyActiveNode);
        onPatched(applyActiveNode);

        const rawModel = toRaw(this.viewEditorModel);
        const resetIsInEdition = () => {
            if (rawModel.isInEdition) {
                rawModel.isInEdition = false;
            }
        };
        onMounted(resetIsInEdition);
        onPatched(resetIsInEdition);

        onError((error) => {
            if (rawModel.isInEdition) {
                this.notification.add(
                    _t(
                        "The requested change caused an error in the view. It could be because a field was deleted, but still used somewhere else."
                    ),
                    {
                        type: "danger",
                    }
                );
                this.viewEditorModel.resetSidebar("view");
                this.viewEditorModel._operations.undo(false);
            } else {
                throw error;
            }
        });

        const config = {
            ...this.env.config,
            onNodeClicked: (xpath, params) => {
                if (params?.discard_studio_click) {
                    return;
                }
                if (this.updateActiveNode({ xpath })) {
                    this.viewEditorModel.activeNodeXpath = xpath;
                }
            },
        };

        if (this.studioViewProps.autoClick) {
            onMounted(this.studioViewProps.autoClick);
        }

        useSubEnv({
            config,
            __beforeLeave__: null,
            __getGlobalState__: null,
            __getLocalState__: null,
            __getContext__: null,
            __getOrderBy__: null,
        });
    }

    updateActiveNode({ xpath, resetSidebarOnNotFound = false }) {
        const vem = this.env.viewEditorModel;
        cleanClickedElements(this.viewRendererRef());
        const el = this.viewRendererRef().querySelector(
            `[data-studio-xpath="${xpath}"], [studioxpath="${xpath}"]`
        );
        if (!el) {
            if (resetSidebarOnNotFound) {
                vem.resetSidebar();
            }
            return false;
        }
        if (vem.editorInfo.editor.styleClickedElement) {
            vem.editorInfo.editor.styleClickedElement(this.viewRendererRef, { xpath });
            return true;
        }
        const clickable = el.closest(".o-web-studio-editor--element-clickable");
        if (clickable) {
            clickable.classList.add("o-web-studio-editor--element-clicked");
        }
        return true;
    }
}
