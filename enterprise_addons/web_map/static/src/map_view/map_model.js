import { _t } from "@web/core/l10n/translation";
import { addPropertyFieldDefs, Model } from "@web/model/model";
import { browser } from "@web/core/browser/browser";
import { formatDateTime, parseDate, parseDateTime } from "@web/core/l10n/dates";
import { KeepLast } from "@web/core/utils/concurrency";
import { deepEqual } from "@web/core/utils/objects";
import { orderByToString } from "@web/search/utils/order_by";
import { user } from "@web/core/user";
import { signal } from "@odoo/owl";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";

const DATE_GROUP_FORMATS = {
    year: "yyyy",
    quarter: "'Q'q yyyy",
    month: "MMMM yyyy",
    week: "'W'WW yyyy",
    day: "dd MMM yyyy",
};

export class MapModel extends Model {
    setup(params, { notification }) {
        this.notification = notification;

        const { closedGroupIds, expandUnlocated, ...metaData } = params;
        this.metaData = metaData;

        this.userPositionStorageKey = `map_user_position,${this.env.config.viewId},${this.env.config.actionId}`;
        const storedUserPosition = browser.localStorage.getItem(this.userPositionStorageKey);
        const parsedUserPosition = storedUserPosition && JSON.parse(storedUserPosition);
        // The browser location isn't cached: only the fact that it should be
        // looked up again is, since coordinates can quickly become stale.
        const cachedUserPosition = parsedUserPosition?.useBrowserLocation
            ? undefined
            : parsedUserPosition;

        this.data = {
            count: 0,
            fetchingCoordinates: false,
            groupByKey: false,
            isGrouped: false,
            partners: {},
            recordGroups: [],
            records: [],
            routes: {},
            shouldUpdatePosition: true,
            ...(cachedUserPosition && { userPosition: cachedUserPosition }),
        };

        this.closedGroupIds = signal(new Set(closedGroupIds));
        this.expandUnlocated = signal(expandUnlocated || false);
        this.keepLast = new KeepLast();
        this.geolocation = new Geolocation();
    }

    /**
     * State to persist across an unmount/remount of the same action (e.g.
     * switching to another view and back).
     */
    get exportedState() {
        return {
            ...this.metaData,
            closedGroupIds: [...this.closedGroupIds()],
            expandUnlocated: this.expandUnlocated(),
        };
    }

    /**
     * @param {any} params
     * @returns {Promise<void>}
     */
    async load(params) {
        this.geolocation.stopFetchingCoordinates();

        const metaData = {
            ...this.metaData,
            ...params,
        };
        if (params.groupBy) {
            await addPropertyFieldDefs(
                this.orm,
                metaData.resModel,
                params.context,
                metaData.fields,
                params.groupBy
            );
        }
        this.data = await this._fetchData(metaData);
        if (!deepEqual(this.metaData.groupBy, metaData.groupBy)) {
            // The closed groups of the previous groupBy are meaningless for the
            // new one: start over from the groups closed by default.
            this.closedGroupIds.set(this._getDefaultClosedGroupIds(this.data));
        }
        this.metaData = metaData;

        this.notify();
    }

    toggleGroup(groupId) {
        const closedIds = new Set(this.closedGroupIds());
        if (closedIds.has(groupId)) {
            closedIds.delete(groupId);
        } else {
            closedIds.add(groupId);
        }
        this.closedGroupIds.set(closedIds);
    }

    toggleUnlocated() {
        this.expandUnlocated.set(!this.expandUnlocated());
    }

    async updateUserPosition(location) {
        const { latitude: prevLat, longitude: prevLong } = this.data.userPosition;
        if (!location) {
            await this._setUserPosition();
            this._saveUserPosition({ useBrowserLocation: true });
        } else {
            this.data.userPosition.address = location.address;
            this.data.userPosition.latitude = location.latitude;
            this.data.userPosition.longitude = location.longitude;
            this._saveUserPosition(this.data.userPosition);
        }
        if (this._shouldUpdateRoutes(prevLat, prevLong)) {
            this.data.routes = await this._fetchRoutes();
            this._notifyFetchedCoordinate(this.data);
        }
    }

    //----------------------------------------------------------------------
    // Protected
    //----------------------------------------------------------------------

    /**
     * Ids of the groups that are folded by default. Only used when the closed
     * groups state is (re)initialized, so that it never overrides the groups
     * the user folded or unfolded.
     *
     * @protected
     * @param {any} data
     * @returns {Set<string>}
     */
    _getDefaultClosedGroupIds(data) {
        return new Set();
    }

    /**
     * Determines whether the routes should be recomputed after changing the
     * current user's position.
     *
     * @protected
     */
    _shouldUpdateRoutes(prevLat, prevLong) {
        const { latitude, longitude } = this.data.userPosition;
        return (
            this.metaData.routing &&
            this.geolocation.useMapBoxAPI &&
            (latitude !== prevLat || longitude !== prevLong)
        );
    }

    /**
     * Adds the corresponding partner to a record.
     *
     * @protected
     */
    _addPartnerToRecord(metaData, data) {
        for (const record of data.records) {
            if (metaData.resModel === "res.partner" && metaData.resPartnerField === "id") {
                record.partner = data.partners[record.id];
            } else {
                record.partner = data.partners[record[metaData.resPartnerField].id];
            }
        }
    }

    /**
     * Handles the case of an empty map.
     * Handles the case where the model is res_partner.
     * Fetches the records according to the model given in the arch.
     * If the records has no partner_id field it is sliced from the array.
     *
     * @protected
     * @params {any} metaData
     * @return {Promise<any>}
     */
    async _fetchData(metaData) {
        const data = {
            count: 0,
            fetchingCoordinates: false,
            groupByKey: metaData.groupBy.length ? metaData.groupBy[0] : false,
            isGrouped: metaData.groupBy.length > 0,
            partners: {},
            recordGroups: [],
            records: [],
            routes: {},
            shouldUpdatePosition: true,
            unlocatedRecords: [],
        };

        //case of empty map
        if (!metaData.resPartnerField) {
            data.recordGroups = [];
            data.records = [];
            data.routes = {};
            await this._fetchUserPosition(data);
            return this.keepLast.add(Promise.resolve(data));
        }
        const results = await this.keepLast.add(this._fetchRecordData(metaData, data));

        const datetimeFields = metaData.fieldNames.filter(
            (name) => metaData.fields[name].type == "datetime"
        );
        for (const record of results.records) {
            // convert date fields from UTC to local timezone
            for (const field of datetimeFields) {
                if (record[field]) {
                    const dateUTC = luxon.DateTime.fromFormat(
                        record[field],
                        "yyyy-MM-dd HH:mm:ss",
                        { zone: "UTC" }
                    );
                    record[field] = formatDateTime(dateUTC, { format: "yyyy-MM-dd HH:mm:ss" });
                }
            }
        }

        data.records = results.records;
        data.count = results.length;
        if (data.isGrouped) {
            data.allRecordGroups = await this._getRecordGroups(metaData, data);
            data.recordGroups = data.allRecordGroups;
        } else {
            data.recordGroups = [];
        }

        if (metaData.resModel === "res.partner" && metaData.resPartnerField === "id") {
            for (const record of data.records) {
                if (!data.partners[record.id]) {
                    data.partners[record.id] = { ...record };
                }
            }
        } else {
            for (const record of data.records) {
                const partner = record[metaData.resPartnerField];
                if (partner && !data.partners[partner.id]) {
                    data.partners[partner.id] = partner;
                }
            }
        }
        await this._fetchUserPosition(data);
        this._addPartnerToRecord(metaData, data);
        this._filterUnlocatedRecords(data);
        this._fetchGeolocationAndRoutes(metaData, data);

        return data;
    }

    _getRecordDomain(metaData) {
        return metaData.domain;
    }

    _getRecordSpecification(metaData, data) {
        const fieldNames = data.groupByKey
            ? metaData.fieldNames.concat(data.groupByKey.split(":")[0].split(".")[0])
            : metaData.fieldNames;
        const specification = {};
        const fieldsToAdd = {
            contact_address_complete: {},
            partner_latitude: {},
            partner_longitude: {},
        };
        for (const fieldName of fieldNames) {
            specification[fieldName] = {};
            if (fieldName === "id" && metaData.resPartnerField === "id") {
                Object.assign(specification, fieldsToAdd);
            } else if (
                ["many2one", "one2many", "many2many"].includes(metaData.fields[fieldName].type)
            ) {
                specification[fieldName].fields = { display_name: {} };
                if (fieldName === metaData.resPartnerField) {
                    Object.assign(specification[fieldName].fields, fieldsToAdd);
                }
            }
        }
        return specification;
    }

    /**
     * Fetch the records for a given model.
     *
     * @protected
     * @returns {Promise}
     */
    _fetchRecordData(metaData, data) {
        const domain = this._getRecordDomain(metaData);
        const specification = this._getRecordSpecification(metaData, data);
        return this.orm.webSearchRead(metaData.resModel, domain, {
            specification,
            limit: metaData.limit,
            offset: metaData.offset,
            order: orderByToString(metaData.defaultOrder || []),
            context: metaData.context,
        });
    }

    _getGroupSourcePosition(data, groupByKey, groupId) {
        return data.userPosition;
    }

    _getGroupDestinationPosition(data, groupByKey, groupId) {
        return data.userPosition;
    }

    /**
     * Determines the origin address (i.e., starting position) for Google Maps routing.
     * If not provided, the current user's location is used instead (default from the API).
     *
     * @param {Number|false} groupId id of the record group, or false if not the view is not grouped
     * @returns {string} address
     */
    _getGroupOriginAddress(groupId) {
        return "";
    }

    async _fetchRoutes(metaData = this.metaData, data = this.data) {
        const hasGeolocation = (p) => p && p.partner_latitude && p.partner_longitude;
        const toCoordinates = (p) => ({
            latitude: p.partner_latitude,
            longitude: p.partner_longitude,
        });

        const groupByKey = data.groupByKey;
        const groups = data.isGrouped ? Object.entries(data.recordGroups) : [["_", data]];
        const promises = groups.map(async ([groupId, group]) => {
            const coords = group.records
                .filter(({ partner }) => hasGeolocation(partner))
                .map(({ partner }) => toCoordinates(partner));
            const source = this._getGroupSourcePosition(data, groupByKey, groupId);
            if (source && source.latitude && source.longitude) {
                coords.unshift(source);
            }
            const destination = this._getGroupDestinationPosition(data, groupByKey, groupId);
            if (destination && destination.latitude && destination.longitude) {
                coords.push(destination);
            }
            const route = await this.geolocation.fetchRoute(coords, metaData.routing);
            return { groupId, route };
        });

        return Promise.all(promises).then((results) => {
            const routesMap = {};
            for (const result of results) {
                if (result) {
                    routesMap[result.groupId] = result.route;
                }
            }
            return routesMap;
        });
    }

    /**
     * Helper to update the user position data, falls back to the company's position
     *
     * @returns {Promise<{lat: number, lon: number} | null>}
     */
    async _fetchUserPosition(data) {
        if (this.data.userPosition?.latitude && this.data.userPosition?.longitude) {
            data.userPosition = this.data.userPosition;
            return;
        }
        data.userPosition = {};
        const permission = await navigator.permissions.query({ name: "geolocation" });
        if (permission.state === "granted") {
            await this._setUserPosition(data);
            this._saveUserPosition({ useBrowserLocation: true });
            return;
        }
        const results = await this.orm
            .cache({ type: "disk" })
            .webRead("res.company", [user.activeCompany.id], {
                specification: {
                    partner_id: {
                        fields: {
                            contact_address_complete: {},
                            partner_latitude: {},
                            partner_longitude: {},
                        },
                    },
                },
            });
        const company = results[0]?.partner_id;
        if (!company) {
            return;
        }
        await this.geolocation.geolocatePartners(company);
        if (!company.partner_latitude || !company.partner_longitude) {
            return;
        }
        data.userPosition.address = company.contact_address_complete;
        data.userPosition.latitude = company.partner_latitude;
        data.userPosition.longitude = company.partner_longitude;
        this._saveUserPosition(data.userPosition);
    }

    /**
     * @protected
     */
    _saveUserPosition(userPosition) {
        browser.localStorage.setItem(this.userPositionStorageKey, JSON.stringify(userPosition));
    }

    async _setUserPosition(data) {
        data = data || this.data;
        return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    data.userPosition.address = "";
                    data.userPosition.longitude = pos.coords.longitude;
                    data.userPosition.latitude = pos.coords.latitude;
                    resolve(true);
                },
                async () => {
                    try {
                        const permission = await navigator.permissions.query({
                            name: "geolocation",
                        });
                        if (permission.state === "denied") {
                            this.notification.add(_t("Location permission required"), {
                                type: "info",
                            });
                        } else {
                            this.notification.add(_t("Unable to get user's location"), {
                                type: "warning",
                            });
                        }
                    } catch {
                        this.notification.add(_t("Unable to get user's location"), {
                            type: "warning",
                        });
                    } finally {
                        resolve(false);
                    }
                }
            );
        });
    }

    /**
     * @protected
     * @returns {Object} the fetched records grouped by the groupBy field.
     */
    async _getRecordGroups(metaData, data) {
        const [fieldName, subGroup] = data.groupByKey.split(":");
        const groupedByProperty = metaData.fields[fieldName.split(".")[0]]?.type === "properties";
        const fieldType = metaData.fields[fieldName].type;
        const unsetName = metaData.fields[fieldName].falsy_value_label || _t("None");
        const groups = {};
        function addToGroup(id, name, record) {
            if (!groups[id]) {
                groups[id] = {
                    name,
                    records: [],
                };
            }
            groups[id].records.push(record);
        }
        for (const record of data.records) {
            const value = groupedByProperty
                ? record[fieldName.split(".")[0]].find((o) => o.name === fieldName.split(".")[1])
                      .value ?? []
                : record[fieldName];
            let id, name;
            if (["one2many", "many2many"].includes(fieldType)) {
                if (value.length) {
                    for (const r of value) {
                        // x2m properties are represented as lists
                        addToGroup(r.id ?? r[0], r.display_name ?? r[1], record);
                    }
                } else {
                    id = name = unsetName;
                    addToGroup(id, name, record);
                }
            } else {
                if (["date", "datetime"].includes(fieldType) && value) {
                    const date = fieldType === "date" ? parseDate(value) : parseDateTime(value);
                    id = name = date.toFormat(DATE_GROUP_FORMATS[subGroup || "month"]);
                } else if (fieldType === "boolean") {
                    id = name = value ? _t("Yes") : _t("No");
                } else if (fieldType === "integer") {
                    id = name = value || "0";
                } else if (fieldType === "selection") {
                    const selected = metaData.fields[fieldName].selection.find(
                        (o) => o[0] === value
                    );
                    id = name = selected ? selected[1] : value;
                } else if (fieldType === "many2one" && value) {
                    id = value.id ?? value[0];
                    name = value.display_name ?? value[1];
                } else {
                    id = value;
                    name = value;
                }
                if (!id && !name) {
                    id = name = unsetName;
                }
                addToGroup(id, name, record);
            }
        }
        return groups;
    }

    /**
     * Notifies the fetched coordinates to server and controller.
     *
     * @protected
     */
    _notifyFetchedCoordinate(data) {
        data.shouldUpdatePosition = false;
        this.notify();
    }

    async _fetchGeolocationAndRoutes(metaData, data) {
        await this._fetchPartnersGeolocation(metaData, data);
        if (this.geolocation.useMapBoxAPI && metaData.routing) {
            data.routes = await this._fetchRoutes(metaData, data);
            this._notifyFetchedCoordinate(data);
        }
    }

    async _fetchPartnersGeolocation(metaData, data) {
        data.fetchingCoordinates = true;
        await this.geolocation.geolocatePartners(Object.values(data.partners), () => {
            this._filterUnlocatedRecords(data);
            this._notifyFetchedCoordinate(data);
        });
        data.fetchingCoordinates = false;
        // Notify to remove the locating ribbon
        this.notify();
    }

    _filterUnlocatedRecords(data) {
        const hasCoordinates = (r) => {
            const latitude = r.partner && r.partner.partner_latitude;
            const longitude = r.partner && r.partner.partner_longitude;
            return latitude && longitude;
        };
        data.unlocatedRecords = data.records.filter((r) => !hasCoordinates(r));
        if (data.isGrouped) {
            data.recordGroups = {};
            for (const [key, group] of Object.entries(data.allRecordGroups)) {
                const records = group.records.filter(hasCoordinates);
                if (records.length) {
                    data.recordGroups[key] = { ...group, records };
                }
            }
        }
    }

    /**
     * Opens googlemaps in a new tab using specified records as waypoints
     *
     * @param { Number | false} groupId which groupId of records to add to url (if false, adds all records)
     * @returns {string}
     */
    googleMapUrl(groupId = false) {
        let url = "https://www.google.com/maps/dir/?api=1";

        let records = this.data.records;
        if (groupId) {
            records = this.data.recordGroups[groupId].records;
        } else if (this.data.isGrouped) {
            records = Object.entries(this.data.recordGroups)
                .filter(([id]) => !this.closedGroupIds().has(id))
                .flatMap(([id, group]) => group.records);
        }
        if (records.length) {
            const allAddresses = records.filter(
                ({ partner }) => partner && partner.contact_address_complete
            );

            const uniqueAddresses = allAddresses.reduce((addrs, { partner }) => {
                const addr = encodeURIComponent(partner.contact_address_complete);
                if (!addrs.includes(addr)) {
                    addrs.push(addr);
                }
                return addrs;
            }, []);

            const originAddress = encodeURIComponent(this._getGroupOriginAddress(groupId));
            if (originAddress) {
                url += `&origin=${originAddress}`;
            }
            if (uniqueAddresses.length && this.metaData.routing) {
                url += `&destination=${uniqueAddresses.pop()}`;
            }
            if (uniqueAddresses.length) {
                url += `&waypoints=${uniqueAddresses.join("|")}`;
            }
        }
        browser.open(url, "_blank");
    }
}

MapModel.services = ["notification"];
