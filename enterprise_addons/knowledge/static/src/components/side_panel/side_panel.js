import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { KnowledgeCommentsPanel } from "@knowledge/comments/comments_panel/comments_panel";
import { KnowledgeArticleChatter } from "@knowledge/components/chatter_panel/chatter_panel";
import { KnowledgeArticleProperties } from "@knowledge/components/properties_panel/properties_panel";
import { KnowledgeTableOfContentPanel } from "@knowledge/components/toc_panel/toc_panel";
import { SidePanelToolbar } from "./side_panel_toolbar";

import { Component, onWillStart, proxy, useProps } from "@odoo/owl";

export class SidePanel extends Component {
    static template = "knowledge.SidePanel";
    static components = {
        SidePanelToolbar,
        KnowledgeArticleProperties,
        KnowledgeArticleChatter,
        KnowledgeCommentsPanel,
        KnowledgeTableOfContentPanel,
    };

    props = useProps(standardWidgetProps);

    setup() {
        this.panelState = proxy(this.env.panelState);

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
        });
    }

    get sidePanelTitle() {
        const panels = [
            ["toc", _t("Table of Contents")],
            ["comments", _t("Comments")],
            ["chatter", _t("Discussions")],
            ["properties", _t("Properties")],
        ];
        return panels.find(([key]) => this.panelState.isDisplayed(key))?.[1] ?? "";
    }

    closeSidePanel() {
        this.panelState.setActivePanel();
    }
}

export const knowledgeSidepanel = {
    component: SidePanel,
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
        { name: "has_item_parent", type: "boolean" },
        { name: "is_listed_in_templates_gallery", type: "boolean" },
        { name: "to_delete", type: "boolean" },
        { name: "user_can_write", type: "boolean" },
    ],
    additionalClasses: ["p-0", "ms-md-2", "d-print-none"],
};

registry.category("view_widgets").add("knowledge_side_panel", knowledgeSidepanel);
