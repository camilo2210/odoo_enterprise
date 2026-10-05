import { Component, t, useProps } from "@odoo/owl";

export class ViewEditorSnackbar extends Component {
    static template = "web_studio.ViewEditor.Snackbar";
    props = useProps({
        operations: t.object(),
        saveIndicator: t.object(),
    });
}
