import { _t } from "@web/core/l10n/translation";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";

import "./autofill";
import "./operational_transform";

import { ListDetailsSidePanel } from "./side_panels/list_details_side_panel";

import { insertList } from "./list_init_callback";
import { NewListSidePanel } from "./side_panels/new_list_sidepanel/new_list_sidepanel";

const { sidePanelRegistry, cellMenuRegistry, unusedDataSourceRegistry } = spreadsheet.registries;

sidePanelRegistry.add("LIST_PROPERTIES_PANEL", {
    title: (env, props) => _t("List #%s", props.listId),
    Body: ListDetailsSidePanel,
    computeState(getters, initialProps) {
        return {
            isOpen: getters.isExistingList(initialProps.listId),
            props: initialProps,
            key: initialProps.listId,
        };
    },
});

sidePanelRegistry.add("NewOdooListSidePanel", {
    title: _t("New Odoo list"),
    Body: NewListSidePanel,
});

initCallbackRegistry.add("insertList", insertList);

cellMenuRegistry.add("sorting_list", {
    separator: false,
    name: _t("Sort list"),
    sequence: 180,
    isReadonlyAllowed: true,
    isVisible: (env) => {
        const position = env.model.getters.getActivePosition();
        if (!env.model.getters.isDynamicList(position)) {
            return false;
        }
        const field = env.model.getters.getListFieldFromPosition(position);
        return !!field;
    },
    icon: "o-spreadsheet-Icon.SORT_RANGE",
    isEnabledOnLockedSheet: true,
});

cellMenuRegistry.addChild("list_sorting_asc", ["sorting_list"], {
    name: _t("Ascending"),
    sequence: 181,
    isActive: (env) => {
        const position = env.model.getters.getActivePosition();
        return env.model.getters.getListFieldSortDirection(position) === "asc";
    },
    execute(env) {
        const position = env.model.getters.getActivePosition();
        const listId = env.model.getters.getListIdFromPosition(position);
        const field = env.model.getters.getListFieldFromPosition(position);
        const listDefinition = env.model.getters.getListDefinition(listId);
        const sortDirection = env.model.getters.getListFieldSortDirection(position);
        const orderBy =
            sortDirection === "none"
                ? [...listDefinition.orderBy, { name: field.name, asc: true }]
                : listDefinition.orderBy.map((order) =>
                      order.name === field.name ? { name: field.name, asc: true } : order
                  );
        env.model.dispatch("UPDATE_ODOO_LIST", {
            listId,
            list: {
                ...listDefinition,
                orderBy,
            },
        });
        env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    },
});

cellMenuRegistry.addChild("list_sorting_desc", ["sorting_list"], {
    name: _t("Descending"),
    sequence: 182,
    isActive: (env) => {
        const position = env.model.getters.getActivePosition();
        return env.model.getters.getListFieldSortDirection(position) === "desc";
    },
    execute(env) {
        const position = env.model.getters.getActivePosition();
        const listId = env.model.getters.getListIdFromPosition(position);
        const field = env.model.getters.getListFieldFromPosition(position);
        const listDefinition = env.model.getters.getListDefinition(listId);
        const sortDirection = env.model.getters.getListFieldSortDirection(position);
        const orderBy =
            sortDirection === "none"
                ? [...listDefinition.orderBy, { name: field.name, asc: false }]
                : listDefinition.orderBy.map((order) =>
                      order.name === field.name ? { name: field.name, asc: false } : order
                  );
        env.model.dispatch("UPDATE_ODOO_LIST", {
            listId,
            list: {
                ...listDefinition,
                orderBy,
            },
        });
        env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    },
});

cellMenuRegistry.addChild("no_list_sorting", ["sorting_list"], {
    name: _t("No sorting"),
    sequence: 183,
    isActive: (env) => {
        const position = env.model.getters.getActivePosition();
        return env.model.getters.getListFieldSortDirection(position) === "none";
    },
    execute(env) {
        const position = env.model.getters.getActivePosition();
        const listId = env.model.getters.getListIdFromPosition(position);
        const field = env.model.getters.getListFieldFromPosition(position);
        const listDefinition = env.model.getters.getListDefinition(listId);
        const orderBy = listDefinition.orderBy?.filter((order) => order.name !== field.name);
        env.model.dispatch("UPDATE_ODOO_LIST", {
            listId,
            list: {
                ...listDefinition,
                orderBy,
            },
        });
        env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    },
});

cellMenuRegistry.add("listing_properties", {
    separator: true,
    name: _t("See list properties"),
    sequence: 190,
    isReadonlyAllowed: true,
    execute(env) {
        const position = env.model.getters.getActivePosition();
        const listId = env.model.getters.getListIdFromPosition(position);
        env.openSidePanel("LIST_PROPERTIES_PANEL", { listId });
    },
    isVisible: (env) => {
        const position = env.model.getters.getActivePosition();
        return (
            !env.services.ui.isSmall &&
            env.model.getters.isExistingList(env.model.getters.getListIdFromPosition(position))
        );
    },
    icon: "o-spreadsheet-Icon.ODOO_LIST",
    isEnabledOnLockedSheet: true,
});

unusedDataSourceRegistry.add("list", {
    type: "list",
    unusedLabel: _t("Unused lists"),
    deleteDataSource: (dispatch, id) => dispatch("REMOVE_ODOO_LIST", { listId: id }),
    getUnusedInstances: (getters) => {
        const unusedLists = [];
        for (const id of getters.getListIds()) {
            if (getters.isListUnused(id)) {
                unusedLists.push({ id, label: getters.getListDisplayName(id) });
            }
        }
        return unusedLists;
    },
});
