import {
    getEditableDescendants,
    StateChangeManager,
    useEmbeddedState,
} from "@html_editor/others/embedded_component_utils";
import {
    ReadonlyFoldableSection,
    readonlyFoldableSectionProps,
} from "@knowledge/editor/embedded_components/core/readonly_foldable_section/readonly_foldable_section";
import { t, useProps } from "@odoo/owl";

export class FoldableSection extends ReadonlyFoldableSection {
    props = useProps({
        ...readonlyFoldableSectionProps,
        host: t.object(),
    });

    setup() {
        super.setup();
        this.state = useEmbeddedState(this.props.host);
    }
    onInputChange(ev) {
        this.env.editorShared.selection.setCursorEnd(
            this.editableDescendants.title.firstElementChild
        );
        super.onInputChange(ev);
    }
}

export const foldableSectionEmbedding = {
    name: "foldableSection",
    Component: FoldableSection,
    getProps: (host) => ({ host }),
    getEditableDescendants: getEditableDescendants,
    getStateChangeManager: (config) => {
        const commitStateChanges = config.commitStateChanges;
        const stateChangeManager = new StateChangeManager(
            Object.assign(config, {
                commitStateChanges: () => {
                    const state = stateChangeManager.getEmbeddedState();
                    config.host.classList.toggle("d-print-none", !state.showContent);
                    commitStateChanges();
                },
            })
        );
        return stateChangeManager;
    },
};
