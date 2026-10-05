import { SearchModel } from "@web/search/search_model";
import { patch } from "@web/core/utils/patch";
import { GROUPABLE_TYPES } from "@web/search/utils/misc";

const CHAR_FIELDS = ["char", "html", "many2many", "many2one", "one2many", "text", "properties"];

patch(SearchModel.prototype, {
    validateField(fieldName, field) {
        const { groupable, type } = field;
        return groupable && fieldName !== "id" && GROUPABLE_TYPES.includes(type);
    },
    async applyAISearch({ filters, groupBys, fieldSearches, customDomain }) {
        // TODO JCB: support fieldProperty
        // TODO JCB: name vs fieldName, which one to use?
        for (const filter of filters || []) {
            if (typeof filter === "string") {
                // Regular filter (string)
                const [searchItem] = this.getSearchItems(
                    (i) => i.type === "filter" && [i.name, i.fieldName].includes(filter)
                );
                if (searchItem && !searchItem?.isActive) {
                    this.toggleSearchItem(searchItem.id);
                }
            } else if (typeof filter === "object" && filter.field_name && filter.selected_periods) {
                // Date filter (object with field_name and selected_periods)
                const [searchItem] = this.getSearchItems(
                    (i) => i.type === "dateFilter" && i.fieldName === filter.field_name
                );
                if (searchItem) {
                    // duplicates doesn't make sense here, e.g. [year-1, fourth_quarter, year-2, fourth_quarter]
                    // likely means the fourth_quarter of both year-1 and year-2.
                    const selectedPeriods = [...new Set(filter.selected_periods)];
                    for (const periodId of selectedPeriods) {
                        this.toggleParentFilter(searchItem.id, periodId);
                    }
                }
            }
        }
        for (const groupBy of groupBys || []) {
            if (typeof groupBy === "string") {
                // Regular groupby (string)
                const [searchItem] = this.getSearchItems(
                    (i) => i.type === "groupBy" && [i.name, i.fieldName].includes(groupBy)
                );

                if (searchItem && !searchItem?.isActive) {
                    this.toggleSearchItem(searchItem.id);
                } else if (!searchItem) {
                    const field = this.searchViewFields[groupBy];
                    if (!field || !this.validateField(groupBy, field)) {
                        continue;
                    }
                    this.createNewGroupBy(groupBy);
                }
            } else if (typeof groupBy === "object" && groupBy.field_name && groupBy.intervals) {
                // Date groupby (object with field_name and intervals)
                const [fstInterval, ...remIntervals] = groupBy.intervals;
                if (!fstInterval) {
                    // nothing to do here if no interval is provided
                    continue;
                }
                const getSearchItem = () => {
                    const [searchItem] = this.getSearchItems(
                        (i) => i.type === "dateGroupBy" && i.fieldName === groupBy.field_name
                    );
                    return searchItem;
                };
                let intervalsToToggle = groupBy.intervals;
                if (!getSearchItem()) {
                    // Create new date groupBy search item for the date field if it doesn't exist
                    const field = this.searchViewFields[groupBy.field_name];
                    if (field && ["date", "datetime"].includes(field.type)) {
                        this.createNewGroupBy(groupBy.field_name, {
                            interval: fstInterval,
                        });
                    }
                    intervalsToToggle = remIntervals;
                }

                const searchItem = getSearchItem();
                for (const interval of intervalsToToggle) {
                    this.toggleDateGroupBy(searchItem.id, interval);
                }
            }
        }
        for (const searchObject of fieldSearches || []) {
            const fieldName = searchObject.search_field;
            const value = searchObject.value;

            const [searchItem] = this.getSearchItems(
                (i) => i.type === "field" && i.fieldName === fieldName
            );
            if (searchItem) {
                this.addAutoCompletionValues(searchItem.id, {
                    value,
                    label: value,
                    operator:
                        searchItem.operator ||
                        (CHAR_FIELDS.includes(searchItem.fieldType) ? "ilike" : "="),
                });
            }
        }
        if (customDomain && customDomain.length) {
            await this.splitAndAddDomain(customDomain);
        }
    },
    async load(config) {
        const result = await super.load(config);
        if (config.ai && !config.state) {
            await this.applyAISearch({
                filters: config.ai.selectedFilters,
                groupBys: config.ai.selectedGroupBys,
                fieldSearches: config.ai.search,
                customDomain: config.ai.customDomain,
            });
        }
        return result;
    },
});
