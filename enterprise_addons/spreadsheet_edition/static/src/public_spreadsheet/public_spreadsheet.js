import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    t,
    types,
    useListener,
    usePlugin,
    useProps,
    xml,
} from "@odoo/owl";
import { location, browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

import { useSpreadsheetNotificationStore } from "@spreadsheet/hooks";

import * as spreadsheet from "@odoo/o-spreadsheet";
import { Spreadsheet } from "@odoo/o-spreadsheet";
import { SpreadsheetSyncStatus } from "../bundle/components/spreadsheet_sync_status/spreadsheet_sync_status";
import { createSpreadsheetCollaborativeModel } from "../bundle/helpers/model";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const {
    topbarMenuRegistry,
    cellMenuRegistry,
    topbarComponentRegistry,
    topBarToolBarRegistry,
    sidePanelRegistry,
} = spreadsheet.registries;

const { Section } = spreadsheet.components;

function readSheetIdFromURL() {
    return new URLSearchParams(location.hash.substring(1)).get("sid") ?? null;
}

function writeSheetIdToURL(sheetId) {
    const url = new URL(location.href);
    const hash = new URLSearchParams(location.hash.substring(1));

    if (hash.get("sid") !== sheetId) {
        hash.set("sid", sheetId);
        url.hash = hash.toString();
        browser.history.replaceState(browser.history.state, null, url);
    }
}

class SyncStatus extends Component {
    static template = xml`
        <SpreadsheetSyncStatus
            t-if="!this.env.model.getters.isReadonly()"
            model="this.env.model"
        />`;
    static components = { SpreadsheetSyncStatus };
}

class UnavailableSidePanel extends Component {
    static template = xml`
        <Section>
            <span>This side panel is not available in the public spreadsheet view.</span>
            <div class="d-flex pt-3">
                <button t-on-click="this.props.onCloseSidePanel" class="o-button">Back</button>
            </div>
        </Section>`;
    props = useProps({
        onCloseSidePanel: types.function(),
    });
    static components = { Section };
}

const SidePanelWhiteList = [
    "ConditionalFormatting",
    "ConditionalFormattingEditor",
    "FindAndReplace",
    "SplitToColumns",
    "RemoveDuplicates",
    "DataValidation",
    "DataValidationEditor",
    "MoreFormats",
    "ColumnStats",
    "TableSidePanel",
    "TableStyleEditorPanel",
    "NamedRangesPanel",
    "PerfProfile",
];

export class PublicSpreadsheet extends Component {
    static template = "spreadsheet_edition.PublicSpreadsheet";
    static components = { Spreadsheet, MainComponentsContainer };

    props = useProps({
        dataUrl: t.string(),
        resModel: t.string(),
        resId: t.number(),
        shareId: t.string().optional(),
        accessToken: t.string(),
        mode: t.string().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        const EMPTY_ACTION = {
            name: "empty",
            sequence: 1,
            isVisible: () => false,
        };
        // replace at component setup to be sure everything was registered before.
        topbarMenuRegistry.replaceChild("pivot_data_sources", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("list_data_sources", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("chart_data_sources", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("refresh_all_data", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("reinsert_static_list", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("reinsert_dynamic_list", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("reinsert_dynamic_pivot", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("reinsert_static_pivot", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("insert_pivot", ["insert"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("reinsert_pivot_cell", ["data"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("insert_list", ["insert"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("insert_carousel", ["insert"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("insert_chart", ["insert"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("command_palette", ["help"], { ...EMPTY_ACTION });
        topbarMenuRegistry.replaceChild("settings", ["file"], { ...EMPTY_ACTION });

        topbarComponentRegistry.remove("filter_component");
        topbarComponentRegistry.replace("spreadsheet_sync_status", {
            component: SyncStatus,
            sequence: 5,
        });

        // remove the table tool to prevent opening the pivot side panel
        // when the selected cell contains a pivot with a table.
        topBarToolBarRegistry.remove("misc");

        cellMenuRegistry.remove("list_see_record");
        cellMenuRegistry.remove("listing_properties");
        cellMenuRegistry.remove("sorting_list");
        cellMenuRegistry.remove("pivot_see_records");
        cellMenuRegistry.remove("pivot_properties");

        // replace non-authorized sidepanels with a placeholder to avoid errors when opening them.
        for (const sidePanelType of sidePanelRegistry.getKeys()) {
            if (!SidePanelWhiteList.includes(sidePanelType)) {
                sidePanelRegistry.replace(sidePanelType, {
                    Body: UnavailableSidePanel,
                    title: sidePanelRegistry.get(sidePanelType).title,
                });
            }
        }

        useSpreadsheetNotificationStore();
        this.http = useService("http");
        this.spreadsheetService = useService("spreadsheet_collaborative");

        useListener(window, "beforeunload", async () => {
            await this.model.leaveSession({ shouldSnapshot: false });
        });

        onWillStart(async () => {
            await this.createModel();
            this.syncSheetFromURL();
        });
        onMounted(() => {
            this.model.on("command-dispatched", this, this.syncURLFromSheet);
        });
        onWillUnmount(() => {
            this.model.off("command-dispatched", this);
        });
    }

    async createModel() {
        this.model = await createSpreadsheetCollaborativeModel({
            env: this.env,
            resModel: this.props.resModel,
            resId: this.props.resId,
            accessToken: this.props.accessToken,
            mode: this.props.mode,
            url: this.props.dataUrl,
        });
        if (this.debugMode.isActive()) {
            // eslint-disable-next-line no-import-assign
            spreadsheet.__DEBUG__ = spreadsheet.__DEBUG__ || {};
            spreadsheet.__DEBUG__.model = this.model;
        }
    }

    syncSheetFromURL() {
        const urlSheetId = readSheetIdFromURL();
        const sheetIds = this.model.getters.getSheetIds();
        const activeSheetId = this.model.getters.getActiveSheetId();
        const targetSheetId = sheetIds.includes(urlSheetId) ? urlSheetId : sheetIds[0];
        if (activeSheetId !== targetSheetId) {
            this.model.dispatch("ACTIVATE_SHEET", {
                sheetIdFrom: activeSheetId,
                sheetIdTo: targetSheetId,
            });
        }
        writeSheetIdToURL(targetSheetId);
    }

    syncURLFromSheet(cmd) {
        if (cmd.type === "ACTIVATE_SHEET" && readSheetIdFromURL() !== cmd.sheetIdTo) {
            writeSheetIdToURL(cmd.sheetIdTo);
        }
    }
}

registry
    .category("public_components")
    .add("spreadsheet_edition.PublicSpreadsheet", PublicSpreadsheet);
