import { Component, usePlugin } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class SidebarPropertiesToolbox extends Component {
    static template = "web_studio.ViewEditor.InteractiveEditorProperties.Toolbox";

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
    }

    get node() {
        return this.env.viewEditorModel.activeNode;
    }

    get nodeType() {
        return this.node.arch.tagName;
    }

    onRemoveFromView() {
        const nodeName = this.node.humanName.toLowerCase();
        let bodyText;
        if (nodeName === "field") {
            const fieldName = this.node.field.string;
            bodyText = _t(
                "Are you sure you want to remove the %(node)s %(field)s from the view?\nIf you need it back, add it from the list of existing fields.",
                {
                    node: nodeName,
                    field: fieldName,
                }
            );
        } else {
            bodyText = _t("Are you sure you want to remove this %(node)s from the view?", {
                node: nodeName,
            });
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Remove %s from view", nodeName),
            body: bodyText,
            confirmLabel: _t("Remove %s", nodeName),
            confirm: () => this.removeNodeFromArch(),
            cancel: () => {},
        });
    }

    async openFormAction() {
        const resId = await this.orm.searchRead(
            "ir.model.fields",
            [
                ["model", "=", this.env.viewEditorModel.resModel],
                ["name", "=", this.node.field.name],
            ],
            ["id"]
        );
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "ir.model.fields",
                res_id: resId[0].id,
                views: [[false, "form"]],
                target: "current",
            },
            { clearBreadcrumbs: true }
        );
    }

    removeNodeFromArch(xpath) {
        const target = this.env.viewEditorModel.getFullTarget(xpath || this.node.xpath);
        const operation = {
            type: "remove",
            target,
        };
        this.env.viewEditorModel.resetSidebar();
        return this.env.viewEditorModel.doOperation(operation);
    }
}
