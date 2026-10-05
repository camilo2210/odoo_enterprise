import {
    PermissionPanel,
    permissionPanelProps,
} from "@knowledge/components/permission_panel/permission_panel";
import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * This component is used exclusively on mobile devices to render the permissions
 * panel within a fullscreen dialog. The fullscreen mode improves usability by
 * providing a more accessible interface for managing article permissions and members.
 */
export class PermissionPanelDialog extends Component {
    static template = "knowledge.PermissionPanelDialog";
    static components = { Dialog, PermissionPanel };

    props = useProps({
        dialogSize: t.string().optional("lg"),
        fullscreen: t.boolean().optional(true),
        title: t.string().optional(_t("Share settings")),
    });

    permissionPanelProps = useProps(permissionPanelProps);
}
