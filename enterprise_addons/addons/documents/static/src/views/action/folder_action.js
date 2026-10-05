import { Component, t, useProps } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useService } from "@web/core/utils/hooks";

/**
 * Allow to define a folder action extending it.
 *
 * The subclass must define:
 * - label member variable (ex.: _t("Edit"))
 * - override the method doActionOnFolder (ex: to open the edit form)
 *
 * And optionally:
 * - icon member variable (ex.: "edit")
 * - icon member class variable (ex. "oi-filled")
 */
export class FolderAction extends Component {
    static template = "documents.FolderAction";
    static components = { DropdownItem };
    props = useProps({
        folder: t.object().optional(),
        env: t.object().optional(),
        close: t.function().optional(),
    });

    static isVisible({ config, searchModel, services }, target, isVisibleAdditional) {
        if (!(config && searchModel && searchModel.resModel === "documents.document" && services)) {
            return false;
        }
        const folder = target || searchModel?.getSelectedFolder();
        const documentService = services["document.document"];
        return (
            folder &&
            documentService &&
            ["kanban", "list"].includes(config.viewType) &&
            (!isVisibleAdditional ||
                isVisibleAdditional({ folder, config, searchModel, documentService }))
        );
    }

    setup() {
        this.icon = "";
        this.action = useService("action");
        this.env = this.props.env || this.env;
    }

    async onItemSelected() {
        let folder = this.props.folder;
        if (!folder) {
            folder = this.env?.searchModel?.getSelectedFolder();
        }
        if (!folder) {
            return;
        }
        this.props.close?.();
        await this.doActionOnFolder(folder);
    }

    async reload() {
        await this.env.searchModel._reloadSearchModel(true);
        await this.env.model.load();
        await this.env.model.notify();
    }

    async doActionOnFolder(folder) {}
}
