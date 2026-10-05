import { useSubEnv } from "@web/owl2/utils";
import { _t } from "@web/core/l10n/translation";
import {
    onMounted,
    onWillStart,
    Component,
    onWillUnmount,
    proxy,
    useListener,
    usePlugin,
    useProps,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { downloadFile } from "@web/core/network/download";
import { user } from "@web/core/user";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { UNTITLED_SPREADSHEET_NAME, DEFAULT_LINES_NUMBER } from "@spreadsheet/helpers/constants";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { initCallbackRegistry } from "@spreadsheet/o_spreadsheet/init_callbacks";
import { RecordFileStore } from "../image/record_file_store";
import { useSpreadsheetCurrencies, useSpreadsheetLocales, useSpreadsheetThumbnail } from "../hooks";
import { InputDialog } from "./input_dialog/input_dialog";
import { OdooDataProvider } from "@spreadsheet/data_sources/odoo_data_provider";
import { CommentsStore } from "../comments/comments_store";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import { createDefaultCurrency } from "@spreadsheet/currency/helpers";
import { SpreadsheetNavbar } from "@spreadsheet_edition/bundle/components/spreadsheet_navbar/spreadsheet_navbar";
import { SpreadsheetComponent } from "@spreadsheet/actions/spreadsheet_component";
import { router } from "@web/core/browser/router";
import { cookie } from "@web/core/browser/cookie";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const { Model } = spreadsheet;
const { useStoreProvider, ModelStore, SidePanelStore } = spreadsheet.stores;
const { UuidGenerator } = spreadsheet.helpers;

/**
 * @typedef SpreadsheetData
 * @property {number} id
 * @property {string} name
 * @property {string} data
 * @property {Object[]} revisions
 * @property {boolean} snapshot_requested
 * @property {Boolean} has_write_access
 * @property {string} [writable_rec_name_field]
 */

export class AbstractSpreadsheetAction extends Component {
    static template = "";
    static components = {
        SpreadsheetComponent,
        SpreadsheetNavbar,
    };
    static target = "fullscreen";

    props = useProps(standardActionServiceProps);

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        if (!this.props.action.params) {
            // the action is coming from a this.trigger("do-action", ... ) of owl (not wowl and not legacy)
            this.params = this.props.action.context;
        } else {
            // the action is coming from wowl
            this.params = this.props.action.params;
        }
        this.isEmptySpreadsheet = this.params.is_new_spreadsheet || false;
        this.resId =
            this.params.resId ||
            this.params.spreadsheet_id || // backward compatibility. res_id used to be spreadsheet_id
            this.params.active_id || // backward compatibility. spreadsheet_id used to be active_id
            (this.props.state && this.props.state.resId); // used when going back to a spreadsheet via breadcrumb
        this.shareId = this.params.share_id || this.props.state?.shareId;
        this.accessToken = this.params.access_token || this.props.state?.accessToken;
        this.actionService = useService("action");
        this.notifications = useService("notification");
        this.dialog = useService("dialog");
        this.orm = useService("orm");
        this.http = useService("http");
        this.ui = useService("ui");
        this.loadLocales = useSpreadsheetLocales();
        this.loadCurrencies = useSpreadsheetCurrencies();
        this.getThumbnail = useSpreadsheetThumbnail();
        this.geoJsonService = useService("geo_json_service");
        this.fileStore = new RecordFileStore(this.resModel, this.resId, this.http, this.orm);
        this.spreadsheetService = useService("spreadsheet_collaborative");
        this.stores = useStoreProvider();
        this.threadId = this.params?.thread_id;
        this.originalMetaViewportContent = document.querySelector(
            'head meta[name="viewport"]'
        ).content;
        this.commandService = useService("command");

        useSetupAction({
            beforeLeave: this._leaveSpreadsheet.bind(this),
            beforeUnload: this._leaveSpreadsheet.bind(this),
            getLocalState: () => ({
                resId: this.resId,
                shareId: this.shareId,
                accessToken: this.accessToken,
                data: this.data,
                model: this.model,
            }),
        });

        useSubEnv({
            download: this.download.bind(this),
            downloadAsJson: this.downloadAsJson.bind(this),
            showHistory: this.showHistory.bind(this),
            insertThreadInSheet: this.insertThreadInSheet.bind(this),
            getLinesNumber: this._getLinesNumber.bind(this),
            getUserLocale: () => this.data && this.data.user_locale,
            openPalette: this.commandService.openMainPalette,
        });
        this.state = proxy({
            spreadsheetName: UNTITLED_SPREADSHEET_NAME,
        });

        onWillStart(async () => {
            if (this.props.state?.model && this.props.state?.data) {
                this._initializeWith(this.props.state.data);
                this.model = this.props.state.model;
                this.model.joinSession();
                this.stores.inject(ModelStore, this.model);
            } else {
                try {
                    const data = await this.fetchData();
                    this._initializeWith(data);
                    this.createModel();
                    this.syncSheetFromRouter();
                    this.stores.inject(ModelStore, this.model);
                } catch {
                    this.notifications.add(
                        "The spreadsheet you’re trying to access doesn’t exist, has been deleted, or you don’t have the necessary permissions to view it.",
                        {
                            type: "info",
                            sticky: true,
                        }
                    );
                    await this.actionService.doAction("menu");
                }
            }
        });
        onMounted(() => {
            document.body.classList.add("o_spreadsheet_edition_o_spreadsheet_action");
            document
                .querySelector('head meta[name="viewport"]')
                .setAttribute(
                    "content",
                    this.originalMetaViewportContent + ", interactive-widget=resizes-content"
                );
            this.execInitCallbacks();
            const commentsStore = this.stores.get(CommentsStore);
            this.props.updateActionState({
                resId: this.resId,
                access_token: this.accessToken || this.data?.access_token,
                share_id: this.shareId,
                sid: this.model.getters.getActiveSheetId(),
            });
            this.env.config.setDisplayName(this.state.spreadsheetName);
            this.model.on("unexpected-revision-id", this, this.onUnexpectedRevisionId.bind(this));
            this.model.on("command-dispatched", this, this.syncRouterFromSheet);
            if (this.threadId) {
                // necessary atm - we need at least one frame to have the right viewport height/width
                setTimeout(() => commentsStore.openCommentThread(this.threadId), 0);
                const sidePanel = this.stores.get(SidePanelStore);
                sidePanel.open("Comments");
            }
        });
        onWillUnmount(() => {
            document.body.classList.remove("o_spreadsheet_edition_o_spreadsheet_action");
            // the meximum scale does not work, need to find another approach
            document
                .querySelector('head meta[name="viewport"]')
                .setAttribute("content", this.originalMetaViewportContent);
            this.model.off("unexpected-revision-id", this);
            this.model.off("command-dispatched", this);
        });
        useListener(window, "afterprint", this.logExport.bind(this));
    }

    get navbarProps() {
        return {
            isReadonly: !this.hasWriteAccess,
            onSpreadsheetNameChanged: this._onSpreadSheetNameChanged.bind(this),
            spreadsheetName: this.state.spreadsheetName,
        };
    }

    get spreadsheetMode() {
        return !this.hasWriteAccess ? "readonly" : "normal";
    }

    async fetchData() {
        // if we are returning to the spreadsheet via the breadcrumb, we don't want
        // to do all the "creation" options of the actions
        if (!this.props.state) {
            await this._setupPreProcessingCallbacks();
        }
        return this._fetchServerData();
    }

    createModel() {
        this.model = new Model(
            this.spreadsheetData,
            this.getModelConfig(),
            this.stateUpdateMessages
        );
        if (this.debugMode.isActive()) {
            // eslint-disable-next-line no-import-assign
            spreadsheet.__DEBUG__ = spreadsheet.__DEBUG__ || {};
            spreadsheet.__DEBUG__.model = this.model;
        }
    }

    getModelConfig() {
        const transportService = this.spreadsheetService.makeCollaborativeChannel(
            this.resModel,
            this.resId,
            this.shareId,
            this.accessToken
        );
        const odooDataProvider = new OdooDataProvider(this.env);
        odooDataProvider.addEventListener("data-source-updated", () => {
            this.model.dispatch("EVALUATE_CELLS");
        });
        return {
            custom: {
                env: this.env,
                orm: this.orm,
                odooDataProvider,
                isFrozenSpreadsheet: this.env.isFrozenSpreadsheet?.(),
            },
            external: {
                fileStore: this.fileStore,
                loadCurrencies: this.loadCurrencies,
                loadLocales: this.loadLocales,
                geoJsonService: this.geoJsonService,
            },
            defaultCurrency: createDefaultCurrency(this.data.default_currency),
            transportService,
            client: {
                id: UuidGenerator.smallUuid(),
                name: user.name,
                userId: user.userId,
            },
            mode: this.spreadsheetMode,
            snapshotRequested: this.snapshotRequested,
            customColors: this.data.company_colors,
            colorScheme: cookie.get("color_scheme"),
        };
    }

    async execInitCallbacks() {
        if (!this.props.state?.model || !this.props.state?.data) {
            if (this.asyncInitCallback) {
                try {
                    this.ui.block();
                    await this.asyncInitCallback(this.model, this.stores);
                } finally {
                    this.ui.unblock();
                }
            }
            if (this.initCallback) {
                this.initCallback(this.model, this.stores);
            }
        }
    }

    async _setupPreProcessingCallbacks() {
        if (this.params.preProcessingAction) {
            const initCallbackGenerator = initCallbackRegistry
                .get(this.params.preProcessingAction)
                .bind(this);
            this.initCallback = await initCallbackGenerator(this.params.preProcessingActionData);
        }
        if (this.params.preProcessingAsyncAction) {
            const initCallbackGenerator = initCallbackRegistry
                .get(this.params.preProcessingAsyncAction)
                .bind(this);
            this.asyncInitCallback = await initCallbackGenerator(
                this.params.preProcessingAsyncActionData
            );
        }
    }

    /**
     * @protected
     * @abstract
     * @param {SpreadsheetData} data
     */
    _initializeWith(data) {
        this.state.spreadsheetName = data.name;
        this.spreadsheetData = data.data;
        this.stateUpdateMessages = data.revisions;
        this.snapshotRequested = data.snapshot_requested;
        this.hasWriteAccess = data.has_write_access;
        this.data = data;
    }

    /**
     * Make a copy of the current document
     * @protected
     */
    async makeCopy() {
        const display_thumbnail = this.getThumbnail();
        const data = this.model.exportData();
        const defaultValues = {
            spreadsheet_data: JSON.stringify(data),
            spreadsheet_snapshot: false,
            spreadsheet_revision_ids: [],
            display_thumbnail,
        };
        const ids = await this.orm.call(this.resModel, "copy", [[this.resId]], {
            default: defaultValues,
        });
        const id = ids[0];
        this._openSpreadsheet(id);
    }

    logExport() {
        this.model.dispatch("LOG_DATASOURCE_EXPORT", { action: "print" });
    }

    /**
     * @private
     */
    async _leaveSpreadsheet() {
        await this.model.leaveSession();
        this.model.off("update", this);
        if (this.hasWriteAccess) {
            return this.onSpreadsheetLeft();
        }
    }

    async _onSpreadSheetNameChanged(detail) {
        const { name } = detail;
        if (name && name !== this.state.spreadsheetName) {
            this.state.spreadsheetName = name;
            this.data.name = name;
            this.env.config.setDisplayName(this.state.spreadsheetName);
            if (this.data.writable_rec_name_field) {
                await this.orm.write(this.resModel, [this.resId], {
                    [this.data.writable_rec_name_field]: name,
                });
            }
        }
    }

    async createNewSpreadsheet() {
        throw new Error("not implemented by children");
    }

    async onSpreadsheetLeft() {
        if (this.accessToken) {
            return;
        }
        await this.orm.write(this.resModel, [this.resId], this.onSpreadsheetLeftUpdateVals());
    }

    onSpreadsheetLeftUpdateVals() {
        return { display_thumbnail: this.getThumbnail() };
    }

    /**
     * @returns {Promise<SpreadsheetData>}
     */
    async _fetchServerData() {
        return this.http.get(`/spreadsheet/data/${this.resModel}/${this.resId}`);
    }

    /**
     * Open a spreadsheet
     * @private
     */
    _openSpreadsheet(spreadsheetId) {
        this.actionService.doAction(
            {
                type: "ir.actions.client",
                tag: this.props.action.tag,
                params: { spreadsheet_id: spreadsheetId },
            },
            { clear_breadcrumbs: true }
        );
    }

    showHistory() {
        this.actionService.doAction(
            {
                type: "ir.actions.client",
                tag: "action_open_spreadsheet_history",
                params: {
                    spreadsheet_id: this.resId,
                    res_model: this.resModel,
                },
            },
            { clear_breadcrumbs: true }
        );
    }

    /**
     * Reload the spreadsheet if an unexpected revision id is triggered.
     */
    onUnexpectedRevisionId() {
        this.actionService.doAction("reload_context");
    }

    /**
     * Sync initial sheet with router (resolve and activate)
     */
    syncSheetFromRouter() {
        if (!this.model) {
            return;
        }
        const urlSheetId = router.current.sid;
        const sheetIds = this.model.getters.getSheetIds();
        const activeSheetId = this.model.getters.getActiveSheetId();
        const targetSheetId = sheetIds.includes(urlSheetId) ? urlSheetId : sheetIds[0];
        if (activeSheetId !== targetSheetId) {
            this.model.dispatch("ACTIVATE_SHEET", {
                sheetIdFrom: activeSheetId,
                sheetIdTo: targetSheetId,
            });
        }
    }

    /**
     * Sync router with the currently activated sheet when activate sheet command dispatch
     */
    syncRouterFromSheet(cmd) {
        if (cmd.type === "ACTIVATE_SHEET" || cmd.type === "DELETE_SHEET") {
            router.replaceState({
                ...router.current,
                sid: this.model.getters.getActiveSheetId(),
            });
        }
    }

    /**
     * Downloads the spreadsheet in xlsx format
     */
    async download() {
        this.ui.block();
        try {
            await waitForDataLoaded(this.model);
            const exportXlsx = await this.model.exportXLSX();
            const sources = this.model.getters.getLoadedDataSources();
            await this.actionService.doAction({
                type: "ir.actions.client",
                tag: "action_download_spreadsheet",
                params: {
                    name: this.state.spreadsheetName,
                    xlsxData: exportXlsx,
                    sources,
                },
            });
        } finally {
            this.ui.unblock();
        }
    }

    /**
     * Downloads the spreadsheet in json format
     */
    async downloadAsJson() {
        this.ui.block();
        try {
            const data = JSON.stringify(this.model.exportData());
            await downloadFile(
                data,
                `${this.state.spreadsheetName}.osheet.json`,
                "application/json"
            );
        } finally {
            this.ui.unblock();
        }
    }

    _getLinesNumber(callback) {
        this.dialog.add(InputDialog, {
            body: _t("Select the number of records to insert"),
            confirm: callback,
            title: _t("Re-insert list"),
            inputValue: DEFAULT_LINES_NUMBER,
            inputType: "number",
        });
    }

    async insertThreadInSheet({ sheetId, col, row }) {
        const [threadId] = await this.env.services.orm.create("spreadsheet.cell.thread", [
            { [this.threadField]: this.resId },
        ]);
        this.model.dispatch("ADD_COMMENT_THREAD", {
            sheetId,
            col,
            row,
            threadId,
        });
        return threadId;
    }
}
