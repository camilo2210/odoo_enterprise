import { _t } from "@web/core/l10n/translation";
import { formatInteger } from '@web/views/fields/formatters';
import { useService } from '@web/core/utils/hooks';
import { Component, onMounted, onWillUnmount, signal, t, useProps } from "@odoo/owl";

export class StreamPostDashboard extends Component {
    static template = "social.KanbanDashboard";

    props = useProps({
        accounts: t.array(),
        isSocialManager: t.boolean(),
        onNewStream: t.function(),
    });

    dashboardRef = signal.ref();

    setup() {
        super.setup();
        this.notification = useService('notification');
        this.orm = useService('orm');
        this.action = useService("action");
        this.popover = [];

        onMounted(() => this._initPopover());

        onWillUnmount(() => this._disposePopover());
    }

    formatStatValue(statValue) {
        return formatInteger(statValue);
    }

    _getRelinkContext(account) {
        return {};
    }

    async _onRelinkAccount(account) {
        if (this.props.isSocialManager) {
            const action = await this.orm.call(
                "social.media",
                "action_add_account",
                [account.media_id[0]],
                { context: this._getRelinkContext(account) }
            );
            this.action.doAction(action);
        } else {
            this.notification.add(
                _t('Sorry, you\'re not allowed to re-link this account, please contact your administrator.'),
                {type: 'danger'}
            );
        }
    }

    _initPopover() {
        this.dashboardRef().querySelectorAll('[data-bs-toggle="popover"]').forEach(el => {
            this.popover.push(new Popover(el, {
                trigger: 'hover',
                delay: {show: 500, hide: 0},
            }));
        });
    }

    _disposePopover() {
        this.popover.forEach((popover) => {
            popover.dispose();
        })
    }

    _hasAudience(account) {
        return true;
    }

    _hasEngagement(account) {
        return true;
    }

    _hasStories(account) {
        return true;
    }

}
