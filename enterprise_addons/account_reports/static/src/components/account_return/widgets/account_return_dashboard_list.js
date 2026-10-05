import { registry } from "@web/core/registry";
import { formatDate, parseDate } from "@web/core/l10n/dates";
import { Component, onWillStart, proxy, usePlugin, useProps } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { ORM } from "@web/core/orm_plugin";
import { ActionPlugin } from "@web/webclient/actions/action_plugin";

const { DateTime } = luxon;


export class AccountReturnDashboardList extends Component {
    static template = "account_reports.account_return_dashboard_list";
    props = useProps(standardWidgetProps);

    orm = usePlugin(ORM);
    action = usePlugin(ActionPlugin);

    state = proxy({ accountReturns: [] });

    setup() {
        onWillStart(this.fetchNextReturns);
    }

    formatReturn(accountReturn) {
        const deadlineDate = parseDate(accountReturn.date_deadline);
        const now = DateTime.now().startOf('day');
        const daysDiff = deadlineDate.diff(now, 'days').days;
        let deadlineClass = '';

        if (daysDiff < 0) {  // Overdue
            deadlineClass = 'text-danger';
        } else if (daysDiff <= 7) {
            deadlineClass = 'text-warning';
        }

        return {
            id: accountReturn.id,
            name: accountReturn.name,
            type_id: accountReturn.type_id,
            matchedReturnsCount: accountReturn.matched_returns_count,
            deadline: formatDate(deadlineDate),
            deadlineClass,
        };
    }
    async fetchNextReturns() {
        const applyReturns = (returns) => {
            this.state.accountReturns = returns.map(this.formatReturn);
        };

        const returns = await this.orm
            .cache({
                type: "disk",
                update: "always",
                callback: (freshReturns, hasChanged) => {
                    if (hasChanged) {
                        applyReturns(freshReturns);
                    }
                },
            })
            .call(
                'account.return',
                'get_next_return_for_dashboard',
                [this.props.record.resId], //allow_multiple_by_types
            );
        applyReturns(returns);
    }

    /**
     * Opens the Tax Return view filtered by return type.
     * @param {Object} accountReturn - The account return object.
     */
    async openTaxReturn(accountReturn) {
        const returnTypeId = accountReturn?.type_id || '';
        const [viewId, searchViewId] = await this.orm.call("account.return", "get_kanban_view_and_search_view_id", [[accountReturn.id]]);

        let action;
        if (accountReturn.matchedReturnsCount === 1) {
            action = await this.orm.call("account.return", "action_open_account_return", [[accountReturn.id]]);
        }
        else {
            // Open the filtered Tax Return view
            action = {
                name: _t("Tax Return"),
                type: 'ir.actions.act_window',
                res_model: 'account.return',
                views: [
                    [viewId || false, 'kanban'],
                    [false, 'calendar'],
                ],
                search_view_id: [searchViewId || false],
                context: {
                    'search_default_groupby_deadline': 1,
                    'search_default_todo_returns': 1,
                    // Apply name filter using return type
                    'search_default_type_id': returnTypeId,
                    'max_number_opened_groups': 100000,
                },
                domain: [['return_type_category', '=', 'account_return']],
            };
        }
        this.action.doAction(action);
    }
}


export const accountReturnDashboardList = {
    component: AccountReturnDashboardList,
}

registry.category("view_widgets").add("account_return_dashboard_list", accountReturnDashboardList);
