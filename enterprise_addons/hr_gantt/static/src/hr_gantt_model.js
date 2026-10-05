import { GanttModel } from "@web_gantt/gantt_model";

export class HrGanttModel extends GanttModel {
    /**
     * @override
     */
    async _fetchData(metaData, additionalContext) {
        /*
        userDomain is the domain the user explicitly wrote in the search bar
        this is used to know whether the user wanted to search only for (e.g.)
        employees, so that the gantt view can include employees that don't have
        (for e.g.) leaves as well.
         */
        const userDomain = this.env.searchModel._getDomain({
            withSearchPanel: false,
            withGlobal: false,
        });
        additionalContext = {
            ...additionalContext,
            user_domain: userDomain,
        };
        await super._fetchData(metaData, additionalContext);
    }
}
