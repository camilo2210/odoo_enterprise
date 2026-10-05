import { Component, useProps, proxy, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { Pager } from "@web/core/pager/pager";
import { useService } from "@web/core/utils/hooks";
import { RecordSelector } from "@web/core/record_selectors/record_selector";

export class OptionsContainer extends Component {
    static template = "web_studio.OptionsContainer";
    props = useProps({
        name: t.string(),
        containerClass: t.any().optional("py-2 px-2 gap-1"),
        slots: t.any(),
    });
}

export class ReportRecordNavigation extends Component {
    static components = {
        OptionsContainer,
        RecordSelector,
        Pager,
    };
    static template = "web_studio.ReportEditor.ReportRecordNavigation";

    setup() {
        this.reportEditorModel = proxy(this.env.reportEditorModel);
    }

    get previewSelectorProps() {
        const currentId = this.reportEditorModel.reportEnv.currentId;
        return {
            resModel: this.reportEditorModel.reportResModel,
            fieldString: this.reportEditorModel.reportEnv.display_name,
            update: (resId) => {
                this.reportEditorModel.loadReportHtml({ resId });
            },
            resId: currentId,
            domain: this.reportEditorModel.getModelDomain(),
            context: { studio: false },
        };
    }

    get previewPagerProps() {
        const { reportEnv } = this.reportEditorModel;
        const { ids, currentId } = reportEnv;
        return {
            limit: 1,
            offset: ids.indexOf(currentId),
            total: ids.length,
        };
    }

    updatePager({ offset }) {
        const ids = this.reportEditorModel.reportEnv.ids;
        const resId = ids[offset];
        this.reportEditorModel.loadReportHtml({ resId });
    }
}

export class UndoRedo extends Component {
    static template = "web_studio.ReportEditor.UndoRedo";
    props = useProps({
        canUndo: t.signal(t.boolean()),
        canRedo: t.signal(t.boolean()),
        undo: t.function(),
        redo: t.function(),
    });
}

export class SaveDiscard extends Component {
    static template = "web_studio.ReportEditor.SaveDiscard";
    props = useProps({
        isDirty: t.signal(t.boolean()),
        save: t.function(),
        discard: t.function(),
    });
}

export class ReportPrintButton extends Component {
    static template = "web_studio.ReportEditor.PrintButton";

    props = useProps({
        onWillPrint: t.function().optional(),
    });

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.reportEditorModel = proxy(this.env.reportEditorModel);
    }

    async printPreview() {
        const model = this.env.reportEditorModel;
        await this.props.onWillPrint?.();
        const recordId = model.reportEnv.currentId || model.reportEnv.ids.find((i) => !!i) || false;
        if (!recordId) {
            this.notification.add(
                _t(
                    "There is no record on which this report can be previewed. Create at least one record to preview the report."
                ),
                {
                    type: "danger",
                    title: _t("Report preview not available"),
                }
            );
            return;
        }

        const action = await rpc("/web_studio/print_report", {
            record_id: recordId,
            report_id: model.editedReportId,
        });
        this.reportEditorModel.renderKey++;
        return this.action.doAction(action, { clearBreadcrumbs: true });
    }
}
