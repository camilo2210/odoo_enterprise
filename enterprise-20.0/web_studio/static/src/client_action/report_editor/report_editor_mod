import { useEnv, useSubEnv } from "@web/owl2/utils";
import { Reactive } from "@web_studio/client_action/utils";
import {
    EventBus,
    markRaw,
    onMounted,
    onWillStart,
    onWillDestroy,
    signal,
    untrack,
    useEffect,
    proxy,
    usePlugin,
} from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { omit, pick } from "@web/core/utils/objects";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useEditorBreadcrumbs } from "@web_studio/client_action/editor/edition_flow";
import { KeepLast } from "@web/core/utils/concurrency";
import { renderToMarkup } from "@web/core/utils/render";
import { makeActiveField } from "@web/model/relational_model/utils";
import { humanReadableError } from "@web_studio/client_action/report_editor/utils";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const notificationErrorTemplate = "web_studio.ReportEditor.NotificationError";
const errorQweb = `<html><div>The report could not be rendered due to an error</div><html>`;

export class ReportEditorModel extends Reactive {
    constructor({ services }) {
        super();
        this.debugMode = usePlugin(DebugModePlugin);
        this.bus = markRaw(new EventBus());
        this._inPreview = false;
        this.mode = "wysiwyg";
        this.warningMessage = "";
        this._isDirty = false;
        this._isInEdition = false;
        this._services = markRaw(services);
        this._errorMessage = false;
        this.paperFormat = {
            margin_top: 0,
            margin_left: 0,
            margin_right: 0,
            print_page_width: 210,
            print_page_height: 297,
        };
        this.reportFields = markRaw({
            id: { name: "id", type: "number" },
            name: { name: "name", type: "char" },
            model: { name: "model", type: "char" },
            report_name: { name: "report_name", type: "char" },
            group_ids: {
                name: "group_ids",
                type: "many2many",
                relation: "res.groups",
                string: _t("Access Groups"),
                relatedFields: {
                    display_name: { type: "char" },
                },
            },
            paperformat_id: {
                name: "paperformat_id",
                type: "many2one",
                relation: "report.paperformat",
                string: _t("Paper format"),
            },
            binding_model_id: {
                name: "binding_model_id",
                type: "many2one",
                relation: "ir.model",
                string: _t("Models"),
            },
            attachment_use: { name: "attachment_use", type: "boolean" },
            attachment: { name: "attachment", type: "char" },
            domain: { name: "domain", type: "char" },
            // fake field
            display_in_print_menu: { name: "display_in_print_menu", type: "boolean" },
        });
        this.reportActiveFields = markRaw({
            id: makeActiveField(),
            name: makeActiveField(),
            model: makeActiveField(),
            report_name: makeActiveField(),
            group_ids: {
                ...makeActiveField(),
                related: {
                    fields: { display_name: { name: "display_name", type: "char" } },
                    activeFields: { display_name: makeActiveField() },
                },
            },
            paperformat_id: makeActiveField(),
            binding_model_id: makeActiveField(),
            attachment_use: makeActiveField(),
            attachment: makeActiveField(),
            domain: makeActiveField(),
            // fake field
            display_in_print_menu: makeActiveField(),
        });
        this.reportEnv = {};
        this.loadHtmlKeepLast = markRaw(new KeepLast());

        this._reportArchs = signal({});
        this.renderKey = 1;
        this.routesContext = pick(user.context, "allowed_company_ids");

        this.resources = markRaw({});
        this.sharedReport = signal(null);
    }

    get reportData() {
        const changes = this._reportChanges;
        const data = this._reportData;
        return changes || data;
    }

    set reportData(_data) {
        const fields = this.reportFields;
        const data = { ..._data };
        for (const [fName, value] of Object.entries(data)) {
            const field = fields[fName];
            if (field.type === "many2one") {
                data[fName] = value && [value.id, value.display_name];
            }
            if (field.type === "many2many") {
                data[fName] = [...value.currentIds];
            }
        }
        this._reportChanges = data;
    }

    get reportResModel() {
        return this._reportData.model;
    }

    get recordToDisplay() {
        return this.reportEnv.currentId || this.reportEnv.ids.find((i) => !!i) || false;
    }

    get editedReportId() {
        return this._services.studio.editedReport.res_id;
    }

    get reportQweb() {
        return this._reportArchs().reportQweb;
    }

    get reportHtml() {
        return this._reportArchs().reportHtml;
    }

    get isDirty() {
        return this._reportChanges || this._isDirty;
    }

    set isDirty(bool) {
        this._isDirty = bool;
    }

    get isInEdition() {
        return this._isInEdition;
    }

    get fullErrorDisplay() {
        return this.debugMode.isActive() ? this._errorMessage : false;
    }

    setInEdition(value) {
        // Reactivity limitation: if we used a setter, the reactivity will trigger the getter
        // thus subscribing us to the key. This is not what we want here.
        value = !!value; // enforce boolean
        if (untrack(() => this._isInEdition) === value) {
            return;
        }
        this._isInEdition = value;
        if (value) {
            this._services.ui.block();
        } else {
            this._services.ui.unblock();
        }
    }

    _resetInternalArchs() {
        // We do this by explicitly bypassing reactivity, we don't want any re-render doing this.
        // _reportsArchs acts as flag, meaning that if one of the arch is not present
        // the relevant function will fetch them. see @loadReportQweb and @loadReportHtml
        const archs = this._reportArchs();
        delete archs.reportQweb;
        delete archs.reportHtml;
    }

    async loadReportEditor() {
        const loaders = [this.loadReportData.bind(this), this.loadModelEnv.bind(this)];
        for (const loader of loaders) {
            if (this.isDestroyed) {
                break;
            }
            await loader();
        }
    }

    async loadReportData() {
        // FIXME introduce alive?
        const data = await rpc("/web_studio/load_report_editor", {
            report_id: this.editedReportId,
            fields: Object.keys(omit(this.reportActiveFields, "display_in_print_menu")),
            context: this.routesContext,
        });
        this._reportData = this._parseFakeFields(data.report_data);
        Object.assign(this.paperFormat, data.paperformat);

        this._errorMessage = data.qweb_error;
        this._reportArchs().reportQweb = data.report_qweb || errorQweb;
        signal.trigger(this._reportArchs);
        this._isLoaded = true;
    }

    async loadReportQweb() {
        if (!this._isLoaded) {
            return;
        }
        if (this._reportArchs().reportQweb) {
            return;
        }

        try {
            const reportQweb = await this.loadHtmlKeepLast.add(
                rpc("/web_studio/get_report_qweb", {
                    report_id: this.editedReportId,
                    context: this.routesContext,
                })
            );
            this._errorMessage = false;
            this._reportArchs().reportQweb = reportQweb;
            signal.trigger(this._reportArchs);
        } catch (e) {
            this._errorMessage = e;
            this._reportArchs().reportQweb = errorQweb;
            signal.trigger(this._reportArchs);
        }
        this.setInEdition(false);
    }

    async loadReportHtml({ resId } = {}) {
        if (!this._isLoaded) {
            return;
        }
        if (resId === undefined && this._reportArchs().reportHtml) {
            return;
        }
        this.reportEnv.currentId = resId !== undefined ? resId : this.reportEnv.currentId;
        try {
            const reportHtml = await this.loadHtmlKeepLast.add(
                rpc("/web_studio/get_report_html", {
                    report_id: this.editedReportId,
                    record_id: this.reportEnv.currentId || 0,
                    context: this.routesContext,
                })
            );
            this._errorMessage = false;
            this._reportArchs().reportHtml = reportHtml;
            signal.trigger(this._reportArchs);
        } catch (e) {
            this._errorMessage = e;
            this._reportArchs().reportHtml = errorQweb;
            signal.trigger(this._reportArchs);
        }
        this.setInEdition(false);
    }

    async saveReport({ htmlParts, urgent, xmlVerbatim } = {}) {
        const hasPartsToSave = htmlParts && Object.keys(htmlParts).length;
        const hasVerbatimToSave = xmlVerbatim && Object.keys(xmlVerbatim).length;
        const hasDataToSave = this.isDirty;
        this.warningMessage = "";
        if (hasVerbatimToSave && hasPartsToSave) {
            throw new Error(_t("Saving both some report's parts and full xml is not permitted."));
        }
        if (this._errorMessage && hasPartsToSave) {
            throw new Error(
                _t("The report is in error. Only editing the XML sources is permitted")
            );
        }
        if (!hasVerbatimToSave && !hasPartsToSave && !hasDataToSave) {
            return false;
        }
        if (!urgent) {
            this.setInEdition(true);
        }

        let result;
        try {
            result = await rpc(
                "/web_studio/save_report",
                {
                    report_id: this.editedReportId,
                    report_changes: this._reportChanges || null,
                    html_parts: htmlParts || null,
                    xml_verbatim: xmlVerbatim || null,
                    record_id: this.reportEnv.currentId || null,
                    context: this.routesContext,
                },
                { silent: urgent }
            );
            this._errorMessage = false;
        } catch (e) {
            this.setInEdition(false);
            const message = renderToMarkup(notificationErrorTemplate, {
                reportName: this._reportData.name,
                recordId: this.reportEnv.currentId,
                error: humanReadableError(e),
            });
            this._services.unProtectedNotification.add(message, {
                type: "warning",
                title: _t("Report edition failed"),
            });
            this.warningMessage = _t("Report edition failed");

            if (this._errorMessage) {
                this._errorMessage = e;
            }

            return false;
        }

        if (hasPartsToSave || hasVerbatimToSave) {
            this._resetInternalArchs();
        }
        const { report_data, paperformat, report_html, report_qweb } = result || {};
        if (!urgent && report_data) {
            this._reportData = this._parseFakeFields(report_data);
            this._reportChanges = null;
            this.paperFormat = paperformat;
        }

        this.isDirty = false;
        if (!urgent) {
            this._reportArchs.set({
                reportHtml: report_html,
                reportQweb: report_qweb,
            });
        }
        this.setInEdition(false);
    }

    discardReport() {
        this.setInEdition(true);
        this.warningMessage = "";
        this.isDirty = false;
        this.renderKey++;
    }

    /**
     * Load and set the report environment.
     *
     * If the report is associated to the same model as the Studio action, the
     * action ids will be used ; otherwise a search on the report model will be
     * performed.
     *
     * @private
     * @returns {Promise}
     */
    async loadModelEnv() {
        if (this.reportEnv.ids) {
            return;
        }
        const modelName = this.reportResModel;
        const result = await this._services.studio.IrModelInfo.read(modelName);

        this.reportEnv = {
            domain: result.domain,
            ids: result.record_ids,
            currentId: result.record_ids[0] || false,
            display_name: result.name,
        };
    }

    getModelDomain() {
        return this.reportEnv.domain;
    }

    _parseFakeFields(reportData) {
        reportData.display_in_print_menu = !!reportData.binding_model_id;
        return reportData;
    }
}

export function useReportEditorModel() {
    const services = Object.fromEntries(["orm", "ui"].map((name) => [name, useService(name)]));
    const env = useEnv();
    services.studio = { ...env.services.studio };
    services.unProtectedNotification = env.services.notification;
    const reportEditorModel = new ReportEditorModel({ services });
    useSubEnv({ reportEditorModel });

    const crumb = proxy({});
    const rem = proxy(reportEditorModel);
    const breadcrumbs = useEditorBreadcrumbs();
    onMounted(() => {
        breadcrumbs.crumbs.length = 0;
        breadcrumbs.push(crumb);
    });
    useEffect(() => {
        crumb.name = rem.reportData?.name;
    });

    onWillStart(() => reportEditorModel.loadReportEditor());
    onWillDestroy(() => (reportEditorModel.isDestroyed = true));

    return proxy(reportEditorModel);
}
