import { effect, proxy, markRaw, computed, status } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FormRenderer } from "@web/views/form/form_renderer";
import { parseXML } from "@web/core/utils/xml";
import { extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { RelationalModel } from "@web/model/relational_model/relational_model";

import { accountReturnCheckKanbanView } from "@account_reports/components/account_return/views/account_return_check_kanban_view";

const viewRegistry = registry.category("views");

class L10nBE_AccountReturnCheckKanbanRenderer extends accountReturnCheckKanbanView.Renderer {
    static template = "l10n_be_reports.account_return_check_kanban_renderer_isoc";
    static components = {
        ...accountReturnCheckKanbanView.Renderer.components,
        FormRenderer,
    };

    setup() {
        super.setup();
        this.isocPaymentFormState = proxy({
            record: undefined,
            archInfo: undefined,
            Compiler: undefined,
        });

        this.shouldShowIsocView = computed(
            () =>
                this.state.record?.data.type_external_id === "l10n_be_reports.be_isoc_prepayment_return_type"
        );
        this.isSubviewReadonly = computed(() => this.state.record?.data.is_completed);

        effect(() => {
            if (this.shouldShowIsocView()) {
                this.loadIsocCustomView();
            }
        });
    }

    async loadIsocCustomView() {
        const resId = this.state.record.data.l10n_be_isoc_payment_form_id.id;
        const resModel = "l10n_be_reports.isoc.prepayment.pay.form";

        const { fields, relatedModels, views } = await this.viewService.loadViews({
            resModel: resModel,
            context: this.props.list.context,
            views: [[undefined, "form"]],
        });

        const { ArchParser, Compiler } = viewRegistry.get("form")
        this.isocPaymentFormState.Compiler = markRaw(Compiler);

        const xmlDoc = parseXML(views["form"].arch);
        this.isocPaymentFormState.archInfo = markRaw(
            new ArchParser().parse(xmlDoc, relatedModels, resModel)
        );

        const extractedFields = extractFieldsFromArchInfo(
            this.isocPaymentFormState.archInfo,
            fields
        );
        const modelConfig = {
            resModel: resModel,
            fields: extractedFields.fields,
            activeFields: extractedFields.activeFields,
            openGroupsByDefault: true,
            isMonoRecord: true,
            groupBy: [],
            resId,
            resIds: [resId],
            context: this.props.list.context,
            mode: "edit",
        };
        const modelParams = {
            config: modelConfig,
            groupsLimit: Number.MAX_SAFE_INTEGER,
            limit: 1,
            countLimit: 1,
        };
        const model = this.scope.run(
            () => new RelationalModel(this.env, modelParams, { orm: this.orm })
        );
        await model.load();

        model.hooks.onRecordChanged = async () => {
            // We need to save the changes in order to load the computed modification on the return card.
            await this.scope.run(() => this.isocPaymentFormState.record._save());
            if (status(this) === "destroyed") return;
            await this.scope.run(() => this.state.record.load());
        };

        this.isocPaymentFormState.record = model.root;
    }
}

viewRegistry.add("be_advance_payment_return_check_kanban", {
    ...accountReturnCheckKanbanView,
    Renderer: L10nBE_AccountReturnCheckKanbanRenderer,
});
