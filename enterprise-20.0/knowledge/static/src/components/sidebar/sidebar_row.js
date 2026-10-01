import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { formatDateTime, deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import MoveArticleDialog from "@knowledge/components/move_article_dialog/move_article_dialog";
import { PermissionPanelDialog } from "@knowledge/components/permission_panel_dialog/permission_panel_dialog";
import { KnowledgeRenamePopover } from "./rename_popover";

import { Component, onWillStart, proxy, signal, t, useProps, useEffect } from "@odoo/owl";

/**
 * The SidebarRow component is responsible of displaying an article (and its
 * children recursively) in a section of the sidebar, and modifying the record
 * of the article.
 */
export class KnowledgeSidebarRow extends Component {
    static template = "knowledge.SidebarRow";
    static components = {
        KnowledgeSidebarRow,
        Dropdown,
        DropdownItem,
    };

    props = useProps({
        article: t.object(),
        unfolded: t.boolean(),
        unfoldedIds: t.instanceOf(Set),
        record: t.object(),
    });

    rootRef = signal.ref();

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.orm = useService("orm");

        this.state = proxy({
            unfolded: false,
        });
        this.renamePopover = usePopover(KnowledgeRenamePopover, {
            closeOnClickAway: true,
            arrow: false,
            position: "bottom",
            withScope: true,
        });
        this.preview = useDropdownState({ onOpen: this.onDropdownOpen.bind(this) });
        this.formatDateTime = formatDateTime;
        this.store = useService("mail.store");

        onWillStart(async () => {
            this.isInternalUser = await user.hasGroup("base.group_user");
            this.canCreateArticle = await user.checkAccessRight("knowledge.article", "create");
        });

        useEffect(() => {
            // Remove the loading spinner when the article is rendered as
            // being unfolded
            if (this.state.loading && this.props.unfolded === true) {
                this.state.loading = false;
            }
        });
    }

    async onDropdownOpen() {
        if (!this.props.article.last_edition_date || !this.props.article.last_edition_uid) {
            const [data] = await this.orm.searchRead(
                this.props.record.resModel,
                [["id", "=", this.props.article.id]],
                ["last_edition_date", "last_edition_uid"]
            );

            const lastEditInfo = {
                last_edition_date: deserializeDateTime(data.last_edition_date),
                last_edition_uid: {
                    id: data.last_edition_uid[0],
                    display_name: data.last_edition_uid[1],
                },
            };
            Object.assign(this.env.getArticle(this.props.article.id), lastEditInfo);
        }
    }

    get hasChildren() {
        return this.props.article.has_article_children;
    }

    get isActive() {
        return this.props.record.resId === this.props.article.id;
    }

    get isLocked() {
        return this.props.article.is_locked;
    }

    get isReadonly() {
        return !this.props.article.user_can_write;
    }

    get lastEditorAvatarUrl() {
        return `/web/image/knowledge.article/${this.props.article.id}/last_edition_user_avatar`;
    }

    get lastEditionDate() {
        return this.props.article.last_edition_date;
    }

    get lastEditor() {
        return this.props.article.last_edition_uid.display_name;
    }

    onLastEditorClick() {
        this.store.openChat({ userId: this.props.article.last_edition_uid.id });
    }

    async toggleFavorite() {
        await this.orm.call("knowledge.article", "action_toggle_favorite", [
            [this.props.article.id],
        ]);
        const record = await this.env.getArticleRecord(this.props.article.id);
        await record.load();
        if (!this.isActive) {
            await this.env.updateSidebarArticles(record);
        }
    }

    async copy() {
        const [articleId] = await this.orm.call("knowledge.article", "action_make_copy", [
            this.props.article.id,
        ]);
        this.env.openArticle(articleId);
    }

    async sendArticleToTrash() {
        if (this.isActive) {
            this.env.sendArticleToTrash();
            return;
        }
        await this.orm.call("knowledge.article", "action_send_to_trash", [this.props.article.id]);
        this.env.bus.trigger("KNOWLEDGE:RELOAD_SIDEBAR", {});
    }

    async openRename() {
        this.renamePopover.open(this.rootRef().querySelector(".o_article_handle"), {
            record: await this.env.getArticleRecord(this.props.article.id),
        });
    }

    openInNew() {
        browser.open(`/knowledge/article/${this.props.article.id}`, "_blank");
    }

    async togglePermissionPanel() {
        const record = await this.env.getArticleRecord(this.props.article.id);
        this.dialog.add(
            PermissionPanelDialog,
            {
                reactiveRecord: () => record,
                openArticle: this.env.openArticle,
                sendArticleToTrash: this.sendArticleToTrash.bind(this),
                fullscreen: false,
                dialogSize: "md",
                title: _t("Share Settings for %(title)s", {
                    title: record.data.display_name || _t("Untitled"),
                }),
            },
            {
                onClose: async () => {
                    await record.save();
                },
            }
        );
    }

    async moveArticle() {
        const record = await this.env.getArticleRecord(this.props.article.id);
        this.dialog.add(
            MoveArticleDialog,
            { knowledgeArticleRecord: record },
            {
                onClose: () => {
                    this.env.bus.trigger("KNOWLEDGE:RELOAD_SIDEBAR", {});
                },
            }
        );
    }

    /**
     * Create a new child article for the row's article.
     */
    createChild() {
        this.env.createArticle(this.props.article.category, this.props.article.id);
    }

    /**
     * (Un)fold the row
     */
    onCaretClick() {
        const isFavorite = Boolean(this.rootRef().closest(".o_favorite_container"));
        if (this.props.unfolded) {
            this.env.fold(this.props.article.id, isFavorite);
        } else if (!this.state.loading) {
            this.state.loading = true;
            // If there are a lot of articles, make sure the rendering caused
            // by the state change and the one cause by the prop update are not
            // done at once, because otherwise the loader will not be shown.
            // If there are not too much articles, the renderings can be done
            // at once so that there is no flickering.
            if (this.props.article.child_ids.length > 500) {
                setTimeout(() => this.env.unfold(this.props.article.id, isFavorite), 0);
            } else {
                this.env.unfold(this.props.article.id, isFavorite);
            }
        }
    }

    /**
     * Open the row's article
     */
    onNameClick() {
        this.env.openArticle(this.props.article.id, {
            sidebarScrollOrigin: this.env.sidebarScrollOrigin,
        });
    }
}
