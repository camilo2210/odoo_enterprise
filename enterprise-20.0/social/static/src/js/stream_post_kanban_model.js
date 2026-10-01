import { RelationalModel } from "@web/model/relational_model/relational_model";
export class StreamPostKanbanModel extends RelationalModel {
    /**
     * Method responsible for refreshing the configured streams.
     * It will be called on view loading as well as when the user clicks on the 'Refresh' button.
     *
     * @private
     */
    _refreshStreams() {
        return this.orm.silent.call('social.stream', 'refresh_all', []);
    }

    /**
     * Method responsible for refreshing the 'dashboard' view of social.accounts.
     * It will be called on view loading as well as when the user clicks on the 'Refresh' button.
     *
     * Also refreshes live.post statistics.
     *
     * @private
     */
    _refreshAccountsStats() {
        this.orm.silent.call('social.live.post', 'refresh_statistics', []);
        return this.orm.silent.call('social.account', 'refresh_statistics', []);
    }

    /**
     * Will load the social.account statistics that are used to populate the dashboard on
     * top of the 'Feed' (social.stream.post grouped by 'stream_id') kanban view.
     *
     * @private
     */
    _loadAccountsStats() {
        return this.orm.call('social.account', 'fetch_statistics');
    }

    /**
     * See 'StreamPostKanbanRenderer#showNoContentHelper'
     * @override
     */
    hasData() {
        return this.root.records.length > 0;
    }

}
