import { Component, onWillStart, proxy, t, useEffect, useProps } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { useEnv, useSubEnv } from "@web/owl2/utils";
import { KnowledgeSidebarRow } from "./sidebar_row";

/**
 * This file defines the different sections used in the sidebar.
 * Each section is responsible of displaying an array of root articles and
 * their children.
 */

/**
 * @abstract
 */
export class KnowledgeSidebarSection extends Component {
    static template = "";
    static components = {
        KnowledgeSidebarRow,
    };

    props = useProps({
        rootIds: t.array(),
        unfoldedIds: t.instanceOf(Set),
        record: t.object(),
    });

    setup() {
        const foldedSections = JSON.parse(browser.localStorage.getItem("knowledge.folded.sections") ?? "{}");
        this.state = proxy({
            isFolded: foldedSections[this.getSectionIdentifier()] || this.props.rootIds.length === 0,
        });

        // Unfold the section of the current article:
        useEffect(() => {
            if (this.props.record.data.category === this.getSectionIdentifier()) {
                this.state.isFolded = false;
            }
        });

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup('base.group_user');
            this.canCreateArticle = await user.checkAccessRight('knowledge.article', 'create');
        });
    }

    toggleSidebarSection() {
        this.state.isFolded = !this.state.isFolded;
        // Persist the new folding state in local storage:
        const foldedSections = JSON.parse(browser.localStorage.getItem("knowledge.folded.sections") ?? "{}");
        foldedSections[this.getSectionIdentifier()] = this.state.isFolded;
        browser.localStorage.setItem("knowledge.folded.sections", JSON.stringify(foldedSections));
    }
}

export class KnowledgeSidebarFavoriteSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarFavoriteSection";

    setup() {
        super.setup();

        const env = useEnv();
        // (Un)fold in the favorite tree by default.
        useSubEnv({
            fold: id => env.fold(id, true),
            sidebarScrollOrigin: "favorites",
            unfold: id => env.unfold(id, true),
        });
    }

    getSectionIdentifier() {
        return "favorites";
    }
}

export class KnowledgeSidebarWorkspaceSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarWorkspaceSection";

    setup() {
        super.setup();
        this.command = useService("command");
    }

    createRoot() {
        this.env.createArticle("workspace");
    }

    searchHiddenArticle() {
        this.command.openMainPalette({searchValue: "$"});
    }

    getSectionIdentifier() {
        return "workspace";
    }
}

export class KnowledgeSidebarSharedSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarSharedSection";

    getSectionIdentifier() {
        return "shared";
    }
}

export class KnowledgeSidebarPrivateSection extends KnowledgeSidebarSection {
    static template = "knowledge.SidebarPrivateSection";

    createRoot() {
        this.env.createArticle("private");
    }

    getSectionIdentifier() {
        return "private";
    }
}
