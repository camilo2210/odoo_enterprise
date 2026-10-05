import { onMounted, usePlugin } from "@odoo/owl";
import { ORM } from "@web/core/orm_plugin";
import { evaluateExpr } from "@web/core/py_js/py";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

const { DateTime } = luxon;


export class AccountReturnBaseKanbanRenderer extends KanbanRenderer
{
    orm = usePlugin(ORM);

    setup() {
        super.setup();

        // Retrieve the allowed categories from xml arch
        const optionsArch = this.props.archInfo.xmlDoc.getAttribute('options');
        this.allowedCategories = ['account_return']
        if (optionsArch) {
            const options = evaluateExpr(optionsArch);
            this.allowedCategories = options.allowed_categories;
        }

        onMounted(() => {this.runAllReturnChecks()});
    }

    async runAllReturnChecks() {
        const additionalDomain = [
            ['date_from', '<=', DateTime.now().endOf("month").toISODate()],
            ['return_type_category', 'in', this.allowedCategories],
        ]

        const returnIds = await this.orm.call(
            'account.return',
            'get_next_returns_ids',
            [
                null,
                additionalDomain,
                true, //allow_multiple_by_types
            ],
        );

        await this.orm.call(
            'account.return',
            'refresh_checks',
            [returnIds]
        );

        // reload records
        await this.props.list.model.load();
    }
}
