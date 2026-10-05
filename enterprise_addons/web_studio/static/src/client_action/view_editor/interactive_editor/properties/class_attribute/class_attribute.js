import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Property } from "@web_studio/client_action/view_editor/property/property";

export class ClassAttribute extends Component {
    static template = "web_studio.ViewEditor.ClassAttribute";
    static components = {
        Property,
    };
    props = useProps({
        value: t.string().optional(),
        onChange: t.function(),
    });
    get tooltip() {
        return _t(
            "Use Bootstrap or any other custom classes to customize the style and the display of the element."
        );
    }
}
