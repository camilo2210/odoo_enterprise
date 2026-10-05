import { Spreadsheet } from "@odoo/o-spreadsheet";
import { SpreadsheetComponent } from "@spreadsheet/actions/spreadsheet_component";
import { makeFakeSpreadsheetService } from "@spreadsheet_edition/../tests/helpers/collaborative_helpers";
import { InsertListSpreadsheetMenu } from "@spreadsheet_edition/assets/list_view/insert_list_spreadsheet_menu_owl";
import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";
import { mockService, patchWithCleanup, contains } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export async function prepareWebClientForSpreadsheet() {
    mockService("spreadsheet_collaborative", makeFakeSpreadsheetService());

    registry.category("favoriteMenu").add(
        "insert-in-spreadsheet-menu",
        {
            Component: InsertListSpreadsheetMenu,
            groupNumber: 4,
            isDisplayed: ({ config }) => {
                const ui = useService("ui");
                return (
                    !ui.isSmall &&
                    config.actionType === "ir.actions.act_window" &&
                    ["kanban", "list"].includes(config.viewType)
                );
            },
        },
        { sequence: 5 }
    );

    // Transforming the canvas into an image might crash in Hoot since the canvas has a size of 0x0 on some test setup
    patchWithCleanup(AbstractSpreadsheetAction.prototype, {
        onSpreadsheetLeftUpdateVals() {
            return { display_thumbnail: "someBase64Image" };
        },
    });
}

function getChildFromComponent(component, cls) {
    return Object.values(component.__owl__.children).find((child) => child.component instanceof cls)
        .component;
}

/**
 * Return the odoo spreadsheet component
 * @param {*} actionManager
 * @returns {SpreadsheetComponent}
 */
export function getSpreadsheetComponent(actionManager) {
    return getChildFromComponent(actionManager, SpreadsheetComponent);
}

/**
 * Return the o-spreadsheet component
 * @param {*} actionManager
 * @returns {Component}
 */
export function getOSpreadsheetComponent(actionManager) {
    return getChildFromComponent(getSpreadsheetComponent(actionManager), Spreadsheet);
}

/**
 * Return the o-spreadsheet Model
 * @return {import("@spreadsheet").OdooSpreadsheetModel} model
 */
export function getSpreadsheetActionModel(actionManager) {
    return getOSpreadsheetComponent(actionManager).model;
}

export function getSpreadsheetActionTransportService(actionManager) {
    return actionManager.transportService;
}

export function getSpreadsheetActionEnv(actionManager) {
    const component = getSpreadsheetComponent(actionManager);
    const oComponent = getOSpreadsheetComponent(actionManager);
    return Object.assign(Object.create(component.env), oComponent.env);
}

/**
 * Change the value of a Select component (that opens a popover on click instead of using the native HTML select)
 */
export async function editSelectComponent(selector, value, skipVisibilityChecks = false) {
    const containArgs = skipVisibilityChecks ? { visible: false, display: false } : {};
    await contains(selector, containArgs).click();
    await contains(`.o-popover .o-select-option[data-id="${value}"]`, containArgs).click();
}

/**
 * Get an item of an open ModelFieldSelector popover
 */
export function getFieldItem(name, fixture) {
    return fixture.querySelector(
        `.o_popover_field_selector .o_model_field_selector_popover_item[data-name="${name}"]`
    );
}
