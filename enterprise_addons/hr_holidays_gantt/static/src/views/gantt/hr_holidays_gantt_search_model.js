import { HrHolidaysSearchModel } from "@hr_holidays/search/hr_holidays_search_model";

export class HrHolidaysGanttSearchModel extends HrHolidaysSearchModel {
    getSearchItems(predicate) {
        // the "Date" group by does not make sense (nor does it work) on a gantt
        // view, so we hide it
        const removeGroupByDate = (item) =>
            item.name !== "group_date_from" && (!predicate || predicate(item));
        return super.getSearchItems(removeGroupByDate);
    }
}
