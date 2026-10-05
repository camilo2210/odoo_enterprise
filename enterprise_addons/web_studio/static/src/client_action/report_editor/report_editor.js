import { Component, providePlugins, usePlugin, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";

import { BaseEditorTabComponent } from "@web_studio/client_action/editor/editor_menu/editor_menu";
import { useReportEditorModel } from "@web_studio/client_action/report_editor/report_editor_model";
import {
    ReportEditorWysiwyg,
    ReportEditorWysiwygSidebar,
} from "@web_studio/client_action/report_editor/report_editor_wysiwyg/report_editor_wysiwyg";
import {
    ReportEditorResourcesPlugin,
    ReportEditorXml,
    ReportResourceSelector,
} from "@web_studio/client_action/report_editor/report_editor_xml/report_editor_xml";
import { ReportEditorPreview } from "./report_editor_preview/report_editor_preview";

import { getCssFromPaperFormat } from "./utils";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";
import { _t } from "@web/core/l10n/translation";
import { ReportEditorSidebar, ReportEditorSidebarPlugin } from "./report_editor_sidebar";
import { ReportPrintButton, ReportRecordNavigation } from "./report_editor_components";

class ReportEditor extends Component {
    static template = "web_studio.ReportEditor";
    static components = {
        ReportEditorSidebar,
        ReportEditorWysiwyg,
        ReportEditorXml,
        ReportEditorPreview,
    };
    props = useProps(standardActionServiceProps);

    setup() {
        this.reportEditorModel = useReportEditorModel();
        providePlugins([ReportEditorSidebarPlugin, ReportEditorResourcesPlugin], {
            reportEditorModel: this.reportEditorModel,
            pages: [
                {
                    title: _t("Editor"),
                    name: "wysiwyg_mode",
                    icon: "edit",
                    mode: "wysiwyg",
                    components: [ReportEditorWysiwygSidebar],
                },
                {
                    title: _t("Preview"),
                    icon: "visibility",
                    name: "preview_mode",
                    mode: "preview",
                    components: [ReportRecordNavigation],
                },
                {
                    title: _t("Sources"),
                    icon: "code",
                    name: "report_edit_sources",
                    mode: "xml",
                    components: [ReportRecordNavigation, ReportResourceSelector],
                },
            ],
        });

        usePlugin(ReportEditorSidebarPlugin).addComponent(ReportPrintButton, "end");
    }

    get paperFormatStyle() {
        const {
            margin_top,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
            header_spacing,
        } = this.reportEditorModel.paperFormat;
        const marginTop = Math.max(0, (margin_top || 0) - (header_spacing || 0));
        return getCssFromPaperFormat({
            margin_top: marginTop,
            margin_left,
            margin_right,
            print_page_height,
            print_page_width,
        });
    }
}
registry.category("actions").add("web_studio.report_editor", ReportEditor);

class ReportsTab extends BaseEditorTabComponent {
    get isDisabled() {
        return !this.modelInfo.record_ids.length;
    }

    get tooltip() {
        if (!this.isDisabled) {
            return false;
        }
        return _t("You cannot edit a report while there is no %(model_name)s (%(model)s)", {
            model_name: this.modelInfo.name,
            model: this.modelInfo.model,
        });
    }
}

registry
    .category("web_studio.editor_tabs")
    .add("reports", { name: _t("Reports"), Component: ReportsTab }, { sequence: 15 });
