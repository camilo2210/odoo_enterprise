import { Plugin } from "@html_editor/plugin";

/**
 * While a freshly opened article hasn't been edited yet, Tab and Enter stay
 * navigation keys instead of editor keys, so the caret can sit in the body
 * without committing to editing:
 * - Tab returns focus to the active sidebar row (SearchPanel-style browsing).
 * - Enter collapses/expands the open parent article (a leaf has nothing to
 *   toggle); neither inserts a newline.
 * The first user keystroke or a click that places the caret in the body
 * commits to editing, after which Tab/Enter fall back to their normal indent /
 * newline behavior.
 */
export class KnowledgeSidebarNavigationPlugin extends Plugin {
    static id = "knowledgeSidebarNavigation";

    setup() {
        this.hasEdited = false;
        this.addDomListener(this.editable, "beforeinput", () => {
            this.hasEdited = true;
        });
        this.addDomListener(this.editable, "pointerdown", () => {
            this.hasEdited = true;
        });
        this.addGlobalDomListener("keydown", this.onKeydown.bind(this), true);
    }

    onKeydown(ev) {
        if (this.hasEdited || !this.editable.contains(ev.target)) {
            return;
        }
        if (ev.key === "Tab" && !ev.shiftKey) {
            const row = this.document.querySelector(
                ".o_knowledge_sidebar .o_article_handle.o_article_active"
            );
            if (row) {
                ev.preventDefault();
                ev.stopImmediatePropagation();
                row.focus();
            }
        } else if (ev.key === "Enter" && !ev.shiftKey) {
            // No newline before the first edit; plain Enter instead toggles the
            // open parent's subtree (a leaf has no caret, so nothing happens).
            // Shift+Enter is left alone: it must still insert a soft line break,
            // which also marks the article as edited.
            ev.preventDefault();
            ev.stopImmediatePropagation();
            this.document
                .querySelector(
                    ".o_knowledge_sidebar .o_article_handle.o_article_active .o_article_caret"
                )
                ?.click();
        }
    }
}
