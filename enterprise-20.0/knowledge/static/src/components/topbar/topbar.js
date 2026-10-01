import { KnowledgeFormStatusIndicator } from "@knowledge/components/form_status_indicator/form_status_indicator";
import KnowledgeHierarchy from "@knowledge/components/hierarchy/hierarchy";
import { PermissionPanel } from "@knowledge/components/permission_panel/permission_panel";
import { PermissionPanelDialog } from "@knowledge/components/permission_panel_dialog/permission_panel_dialog";
import { Component, computed, onWillStart, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { useStatusIndicator } from "@web/views/form/form_status_indicator/form_status_indicator";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { SidePanelToolbar } from "../side_panel/side_panel_toolbar";

class KnowledgeTopbar extends Component {
    static template = "knowledge.KnowledgeTopbar";
    static components = {
        KnowledgeHierarchy,
        SidePanelToolbar,
        KnowledgeFormStatusIndicator,
    };

    props = useProps(standardWidgetProps);

    reactiveRecord = computed(() => this.props.record);

    setup() {
        this.dialog = useService("dialog");
        this.uiService = useService("ui");
        this.panelState = proxy(this.env.panelState);
        this.statusIndicator = useStatusIndicator(this.props.record.model, {
            save: () => this.env.save(),
            discard: () => this.env.discard(),
        });
        this.state = proxy({
            shareBtnIsActive: false,
        });
        this.permissionPopover = usePopover(PermissionPanel, {
            closeOnClickAway: true,
            arrow: false,
            onClose: () => (this.state.shareBtnIsActive = false),
            position: "bottom-end",
        });
        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
        });
    }

    togglePermissionPanel(event) {
        if (this.uiService.isSmall && !this.state.shareBtnIsActive) {
            this.dialog.add(PermissionPanelDialog, {
                reactiveRecord: this.reactiveRecord,
                openArticle: this.env.openArticle,
                sendArticleToTrash: this.env.sendArticleToTrash,
            });
        } else if (this.permissionPopover.isOpen) {
            this.permissionPopover.close();
        } else {
            if (this.props.record.dirty) {
                this.props.record.save();
            }
            this.permissionPopover.open(event.currentTarget, {
                reactiveRecord: this.reactiveRecord,
                openArticle: this.env.openArticle,
                sendArticleToTrash: this.env.sendArticleToTrash,
            });
            this.state.shareBtnIsActive = true;
        }
    }

    get favoriteButtonTitle() {
        return this.props.record.data.is_user_favorite
            ? _t("Remove from favorites")
            : _t("Add to favorites");
    }
}

export const knowledgeTopbar = {
    component: KnowledgeTopbar,
    fieldDependencies: [
        { name: "create_uid", type: "many2one", relation: "res.users" },
        { name: "display_name", type: "char" },
        { name: "last_edition_uid", type: "many2one", relation: "res.users" },
        { name: "active", type: "boolean" },
        { name: "article_properties", type: "jsonb" },
        { name: "cover_image_id", type: "many2one", relation: "knowledge.cover" },
        { name: "full_width", type: "boolean" },
        { name: "icon", type: "char" },
        { name: "inherited_permission", type: "char" },
        { name: "inherited_permission_parent_id", type: "many2one", relation: "knowledge.article" },
        { name: "is_article_item", type: "boolean" },
        { name: "is_locked", type: "boolean" },
        { name: "is_desynchronized", type: "boolean" },
        { name: "is_user_favorite", type: "boolean" },
        { name: "name", type: "char" },
        { name: "parent_id", type: "char" },
        { name: "parent_emoji", type: "char" },
        { name: "parent_path", type: "char" },
        { name: "root_article_id", type: "many2one", relation: "knowledge.article" },
        { name: "root_article_emoji", type: "char" },
        { name: "has_item_parent", type: "boolean" },
        { name: "is_listed_in_templates_gallery", type: "boolean" },
        { name: "to_delete", type: "boolean" },
        { name: "user_can_write", type: "boolean" },
    ],
};

registry.category("view_widgets").add("knowledge_topbar", knowledgeTopbar);
