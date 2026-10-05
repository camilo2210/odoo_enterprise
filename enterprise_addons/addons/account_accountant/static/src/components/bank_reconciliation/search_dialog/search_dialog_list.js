import { useProps, proxy, t } from "@odoo/owl";
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer, listRendererProps } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { standardViewProps } from "@web/views/standard_view_props";

export class BankRecReconcileDialogListController extends ListController {
    static template = "account_accountant.BankRecReconcileDialogListView";
    // Inline copy of ListController's props schema (no exported const upstream)
    props = useProps({
        ...standardViewProps,
        allowSelectors: t.boolean().optional(true),
        onSelectionChanged: t.function().optional(),
        readonly: t.boolean().optional(),
        allowOpenAction: t.boolean().optional(true),
        Model: t.function(),
        Renderer: t.function(),
        buttonTemplate: t.string(),
        archInfo: t.object(),
        createRecord: t.function().optional(() => () => {}),
        selectRecord: t.function().optional(() => () => {}),
        bankRecInfo: t.object().optional(),
    });

    async onSelectionChanged() {
        this.props.bankRecInfo.onSelectionChanged(this);
    }
}

export class BankRecReconcileDialogListRenderer extends ListRenderer {
    static template = "account_accountant.BankRecReconcileDialogListRenderer";
    static recordRowTemplate = "account_accountant.BankRecReconcileDialogListRenderer.RecordRow";
    props = useProps({
        ...listRendererProps,
        bankRecInfo: t.any().optional(),
    });

    setup() {
        super.setup();
        if (this.props.bankRecInfo?.state) {
            this.bankRecState = proxy(this.props.bankRecInfo.state);
        }
    }

    async openMoveView(record) {
        this.env.services.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: record.data.move_id.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

export const bankRecReconcileDialogListRenderer = {
    ...listView,
    Renderer: BankRecReconcileDialogListRenderer,
    Controller: BankRecReconcileDialogListController,
    props: (genericProps, view) => {
        const baseProps = listView.props(genericProps, view);
        return {
            ...baseProps,
            bankRecInfo: genericProps.bankRecInfo,
        };
    },
};

registry.category("views").add("bank_rec_dialog_list", bankRecReconcileDialogListRenderer);
