import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { onWillStart, signal, useScope, usePlugin, status } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { parseXML } from "@web/core/utils/xml";
import { extractFieldsFromArchInfo } from "@web/model/relational_model/utils";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { isNull } from "@web/views/utils";
import { AccountReturnKanbanRecord } from "./account_return_kanban_record";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { focusNextFlatCard } from "./account_return_kanban_renderer";
import { GlobalBusPlugin } from "@web/core/global_bus_plugin";
import { ORM } from "@web/core/orm_plugin";
import { useEnv } from "@web/owl2/utils";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";


const viewRegistry = registry.category("views");


export class AccountReturnCheckKanbanRenderer extends KanbanRenderer {
    static template = "account_reports.account_return_check_kanban_renderer";

    static components = {
        ...KanbanRenderer.components,
        AccountReturnKanbanRecord,
        Chatter,
    };

    checkCardsRef = signal.ref();

    orm = usePlugin(ORM);
    action = usePlugin(ActionPlugin);
    viewService = useService("view");   

    record = signal(undefined);

    bus = usePlugin(GlobalBusPlugin).bus;
    scope = useScope();

    setup() {
        super.setup();
        const context = this.props.list.context;

        if (context.active_model === "account.return") {
            this.currentReturnId = context.active_id;

            useBus(this.bus, "return_reload_model", async (ev) => {
                const recordIds = ev.detail.resIds;
                if (recordIds.includes(this.currentReturnId)) {
                    await this.props.list.model.load();
                }
            });

            onWillStart(async () => {
                if (!this.currentReturnId) return;

                const { fields, relatedModels, views } = await this.viewService.loadViews({
                    resModel: "account.return",
                    context: context,
                    views: [[context.account_return_view_id, "kanban"]],
                });
                const { ArchParser } = viewRegistry.get("kanban");
                const xmlDoc = parseXML(views["kanban"].arch);
                this.returnArchInfo = new ArchParser().parse(xmlDoc, relatedModels, 'account.return');
                const extractedFields = extractFieldsFromArchInfo(this.returnArchInfo, fields);

                // The model is instantiated outside of a synchronous setup (in an async hook), so we
                // run it in the component's scope for `usePlugin()` (e.g. the offline plugin) to resolve.
                const model = this.scope.run(
                    () => new RelationalModel(useEnv(), this.getReturnModelParams({ ...context, in_checks_view: true }, extractedFields.activeFields, extractedFields.fields, this.currentReturnId), {orm: this.orm})
                );
                await model.load();

                const originalChecksLoadFunction = this.props.list.model.load.bind(this.props.list.model);
                this.props.list.model.load = async (params) => {
                    if (status(this) === "destroyed") return;

                    // Reload return card
                    const result = await this.scope.run(() => originalChecksLoadFunction(params));
                    if (status(this) === "destroyed") return;

                    await this.scope.run(() => this.record().load());
                    if (status(this) === "destroyed") return;
                    // Reload chatter messages
                    this.scope.run(
                        () => this.bus.trigger("MAIL:RELOAD-THREAD", {
                            model: "account.return",
                            id: this.currentReturnId,
                        })
                    );

                    return result;
                };

                this.record.set(model.root);

                // Update records checks
                const records = this.props.list.records;
                if (records.length > 0) {
                    const checkResults = this.orm.call("account.return", "refresh_checks", [this.currentReturnId])
                    checkResults.then(() => {
                        this.scope.run(async () => {
                            await this.props.list.model.load();
                        })
                    });
                }
            });
        }
    }

    getReturnModelParams(context, activeFields, fields, resId) {
        const modelConfig = {
            resId: resId,
            resIds: [resId],
            context: context,
            resModel: 'account.return',
            fields,
            activeFields,
            openGroupsByDefault: true,
            isMonoRecord: true,
            mode: 'readonly',
        };

        return {
            config: modelConfig,
            groupsLimit: Number.MAX_SAFE_INTEGER,
            limit: 1,
            countLimit: 1,
        };
    }

    get groups() {
        const { list } = this.props;
        if (!list.isGrouped) {
            return false;
        }
        return list.groups.map((group, index) => ({
            ...group,
            key: isNull(group.value) ? `group_key_${index}` : String(group.value),
        }));
    }

    focusNextCard(area, direction) {
        return focusNextFlatCard(area, direction);
    }

    async openRecord(record, params) {
        const recordId = record.resId;
        if (record.resModel === "account.return.check") {
            const result = await this.orm.call(
                record.resModel,
                "action_review",
                [recordId]
            );

            if (result) {
                this.action.doAction(result);
            }
        }
    }
}
