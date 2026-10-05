import { Component, useProps, t } from "@odoo/owl";

/**
 * Generic component that defines the general structure of an action button.
 */
export class ActionButton extends Component {
    props = useProps({
        extraClass: t.string().optional(""),
        innerExtraClass: t.string().optional(""),
        hideLabel: t.boolean().optional(),
        icon: t.string(),
        iconClass: t.string().optional(),
        name: t.string().optional(),
        onClick: t.function().optional(() => () => {}),
        title: t.string().optional(),
        type: t.string().optional("secondary"),
        inCallPad: t.boolean().optional(),
        disabled: t.boolean().optional(),
        isSmall: t.boolean().optional(),
        isOpen: t.boolean().optional(),
    });
    static template = "voip.ActionButton";
}
