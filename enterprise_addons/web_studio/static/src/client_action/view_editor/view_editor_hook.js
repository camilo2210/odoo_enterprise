import { onWillDestroy, onWillStart, proxy, useScope } from "@odoo/owl";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import { useEnv, useSubEnv } from "@web/owl2/utils";
import {
    useEditorBreadcrumbs,
    useEditorMenuItem,
} from "@web_studio/client_action/editor/edition_flow";
import { viewTypeToString } from "@web_studio/studio_service";
import { ViewEditorModel } from "./view_editor_model";
import { ViewEditorSnackbar } from "./view_editor_snackbar";

export function useViewEditorModel(viewRef, { initialState }) {
    const env = useEnv();

    /* Services */
    const services = Object.fromEntries(
        ["orm", "ui", "notification"].map((sName) => [sName, useService(sName)])
    );
    // Capture studio's state as a new Object. This is due to concurrency
    // issues because we are an action, and rendering may be caused by other things (reactives)
    services.studio = { ...env.services.studio };
    services.dialog = { add: useOwnedDialogs() };

    /* Coordination */
    // Communicates with editorMenu, provides standard server calls
    const editionFlow = proxy(env.editionFlow);
    useEditorBreadcrumbs({ name: viewTypeToString(services.studio.editedViewType) });

    const viewEditorModel = new ViewEditorModel({
        env,
        services,
        editionFlow,
        viewRef,
        initialState,
    });
    useSubEnv({ viewEditorModel });

    const { _snackBar, _operations } = viewEditorModel;
    useEditorMenuItem({
        component: ViewEditorSnackbar,
        props: { operations: _operations, saveIndicator: _snackBar },
    });

    const scope = useScope();
    onWillStart(
        async () =>
            new Promise((resolve, reject) => {
                viewEditorModel
                    .load()
                    .then(resolve)
                    .catch((error) => {
                        if (scope.status !== 3 /* destroyed */) {
                            reject(error);
                        }
                    });
            })
    );

    onWillDestroy(() => {
        viewEditorModel.isInEdition = false;
    });
    return proxy(viewEditorModel);
}

export function useSnackbarWrapper(fn) {
    const env = useEnv();
    return env.viewEditorModel._decorateFunction(fn);
}
