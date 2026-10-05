import { render } from "@web/owl2/utils";
import { useService } from "@web/core/utils/hooks";
import { fuzzyTest } from "@web/core/utils/search";

import { DocumentsSearchPanel } from "@documents/views/search/documents_search_panel";

import { Component, onWillStart, proxy, signal, t, useProps } from "@odoo/owl";

/**
 * This class is used to merge the required parts of the search model and search panel
 * to allow selecting a folder in a tree-like view.
 */
export class DocumentsSearchPanelUserFolderId extends Component {
    static excludedValues = ["RECENT", "TRASH"];
    static template = "documents.SearchPanelUserFolderId";
    static subTemplates = {
        category: "documents.SearchPanel.Category.Operations",
    };
    static rootIcons = DocumentsSearchPanel.rootIcons;
    props = useProps({
        value: t.string(),
        onChange: t.function(),
        ulClass: t.string().optional(),
    });

    searchInputRef = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.uiService = useService("ui");
        const activeValueId = isNaN(this.props.value)
            ? this.props.value
            : parseInt(this.props.value);
        this.state = proxy({
            // 1 is section/category Id as there is only one, but we use a template that needs this.
            active: { 1: activeValueId },
            expanded: { 1: {} },
        });
        this.category = {
            activeValueId,
            description: "Folders",
            icon: "folder",
            iconClass: "oi-filled",
            id: 1,
            rootIds: [false],
            values: new Map([
                [
                    false,
                    {
                        childrenIds: [],
                        display_name: "All",
                        id: false,
                        bold: true,
                        parentId: false,
                    },
                ],
            ]),
        };
        this._treeValues = [];

        onWillStart(async () => {
            const result = await this.orm.call(
                "documents.document",
                "search_panel_select_range",
                ["user_folder_id"],
                {}
            );
            const values = result.values
                .filter((v) => !this.constructor.excludedValues.includes(v.id))
                .sort((a) => (a.id === "MY" ? -1 : 1));
            this._treeValues = values;
            this._createCategoryTree({ values, initialValue: activeValueId });
        });
    }

    get sections() {
        return new Map([[1, this.categories[0]]]);
    }

    get ulClass() {
        return this.props.ulClass || "";
    }

    isUploadingInFolder() {
        return false;
    }

    async toggleCategory(category, value) {
        const newActiveValueId = value.id;
        if (category.activeValueId !== newActiveValueId) {
            this.props.onChange(newActiveValueId.toString(), value);
            category.activeValueId = newActiveValueId;
            this.state.active[1] = newActiveValueId;
        }
    }

    async toggleFold(category, value) {
        const categoryState = this.state.expanded[category.id];
        categoryState[value.id] = !categoryState[value.id];
    }

    onFoldKeyDown(ev, category, value) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.toggleFold(category, value);
        }
    }

    onFilterChange(ev) {
        const query = ev.target.value;
        this._createCategoryTree({ values: this._treeValues, query });
        render(this);
    }

    onClickClear() {
        this.searchInputRef().value = "";
        this.searchInputRef().dispatchEvent(new CustomEvent("change", { detail: { value: "" } }));
    }

    /**
     * Extend Search Panel's method to filter folders on search query
     *
     * @param { Object[] } values Fetched values from search_panel_select_range
     * @param { String? } query Show folders and parents fuzzy matching `query`
     * @param { Number } initialValue expand to this id
     */
    _createCategoryTree({ values, query, initialValue }) {
        // Match ids to construct the tree
        for (const value of values) {
            if (!isNaN(value.user_folder_id)) {
                value.user_folder_id = Number(value.user_folder_id);
            }
        }
        const category = this.category;
        const lowercaseQuery = query?.toLowerCase();
        const newCategoryValues = new Map();
        for (const value of values) {
            const parentId = value["user_folder_id"] || false;
            newCategoryValues.set(
                value.id,
                Object.assign({}, value, {
                    parentId,
                    childrenIds: [],
                })
            );
        }

        for (const [id, node] of newCategoryValues.entries()) {
            const parentId = node.parentId;
            if (parentId && newCategoryValues.has(parentId)) {
                newCategoryValues.get(parentId).childrenIds.push(id);
            }
        }

        let idsToInclude = new Set(newCategoryValues.keys());
        const newExpanded = {};

        if (lowercaseQuery) {
            const matchingIds = new Set();
            for (const [id, node] of newCategoryValues.entries()) {
                if (!node.parentId && !node.user_folder_id) {
                    continue;
                }
                if (node.display_name && fuzzyTest(lowercaseQuery, node.display_name)) {
                    matchingIds.add(id);
                }
            }

            const relevantIds = new Set(matchingIds);

            // Identify and expand results ancestors
            for (const id of matchingIds) {
                let current = newCategoryValues.get(id);
                while (current?.parentId && newCategoryValues.has(current.parentId)) {
                    const parentId = current.parentId;
                    relevantIds.add(parentId);
                    newExpanded[parentId] = true;
                    current = newCategoryValues.get(parentId);
                }
            }

            // Add descendants
            const collectDescendants = (id) => {
                const node = newCategoryValues.get(id);
                if (!node) {
                    return;
                }
                for (const childId of node.childrenIds) {
                    if (!relevantIds.has(childId)) {
                        relevantIds.add(childId);
                        collectDescendants(childId);
                    }
                }
            };
            for (const id of matchingIds) {
                collectDescendants(id);
            }

            // Always show available roots in "My Drive", "Company"
            for (const [id, node] of newCategoryValues.entries()) {
                if (!node.parentId) {
                    relevantIds.add(id);
                }
            }
            idsToInclude = relevantIds;
        } else {
            // No query, include everything, expand roots
            for (const [id, node] of newCategoryValues.entries()) {
                if (!node.parentId) {
                    newExpanded[id] = true;
                }
            }
            // expand ancestors if there is an initial value
            const ancestors = this.getFolderAndParents(newCategoryValues, initialValue);
            for (const folder of ancestors) {
                if (!newExpanded[folder.id]) {
                    newExpanded[folder.id] = true;
                }
            }
        }

        this.state.expanded[1] = newExpanded;

        this._setCategoryValues(category, idsToInclude, newCategoryValues);

        // collect rootIds
        category.rootIds = [false];
        for (const [id, node] of category.values.entries()) {
            if (!node.parentId || !category.values.has(node.parentId)) {
                category.rootIds.push(id);
            }
        }
    }

    _setCategoryValues(category, idsToInclude, categoryMap) {
        for (const folderId of category.values.keys()) {
            if (typeof folderId === "number") {
                category.values.delete(folderId);
            }
        }
        for (const id of idsToInclude) {
            if (categoryMap.has(id)) {
                const node = Object.assign({}, categoryMap.get(id), {
                    childrenIds: [], // to be rebuilt below
                });
                category.values.set(id, node);
            }
        }
        for (const [id, node] of category.values.entries()) {
            const parentId = node.parentId;
            if (parentId && category.values.has(parentId)) {
                category.values.get(parentId).childrenIds.push(id);
            }
        }
    }

    getFolderAndParents(categoryValues, initialValue) {
        let folder = categoryValues.get(initialValue);
        const folders = [];
        while (folder) {
            folders.push(folder);
            folder = folder.folder_id
                ? categoryValues.get(folder.folder_id)
                : categoryValues.get(folder.user_folder_id);
        }
        return folders;
    }
}
