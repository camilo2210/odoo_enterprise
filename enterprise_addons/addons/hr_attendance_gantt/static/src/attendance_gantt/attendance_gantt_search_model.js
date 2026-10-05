import { SearchModel } from "@web/search/search_model";

export class AttendanceGanttSearchModel extends SearchModel {
    getSearchItems(predicate) {
        // the "Date" group by does not make sense (nor does it work) on a gantt
        // view, so we hide it
        const removeGroupByDate = (item) => {
            if (["groupby_month", "groupby_week"].includes(item.name)) {
                return false;
            }
            return !predicate || predicate(item);
        };
        return super.getSearchItems(removeGroupByDate);
    }
}
