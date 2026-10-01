export function userHasContractPeriods(row, column, key) {
    const { workingPeriods } = this.model.data;
    if (!workingPeriods) {
        return true;
    }
    const resourceId = Object.assign({}, ...JSON.parse(row.id))[key]?.[0]
    const periods = workingPeriods[resourceId];
    if (periods?.length) {
        const { interval } = this.model.metaData.scale;
        const left = column.start.startOf(interval);
        const right = column.stop.startOf(interval);
        return periods.some(
            ({ start, end }) =>
                start.startOf(interval) <=  left &&
                (!end ||
                    end.startOf(interval) >= right)
        );
    }
    return periods === undefined;
}
