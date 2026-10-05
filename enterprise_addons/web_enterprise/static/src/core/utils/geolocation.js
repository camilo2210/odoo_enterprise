import { _t } from "@web/core/l10n/translation";
import { delay } from "@web/core/utils/concurrency";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const MB_ERROR_MESSAGES = {
    "Route exceeds maximum distance limitation": _t("Some routing points are too far apart"),
    "Too Many Requests": _t("Too many requests, try again in a few minutes"),
};

function hasValidCoordinates(partner) {
    return (
        partner.partner_latitude &&
        partner.partner_longitude &&
        partner.partner_latitude >= -90 &&
        partner.partner_latitude <= 90 &&
        partner.partner_longitude >= -180 &&
        partner.partner_longitude <= 180
    );
}

/**
 * Geolocation service handling address translation (from and to coordinates), partner geocoding, and routing.
 * It dynamically switches between MapBox (https://www.mapbox.com/) and OpenStreetMap (https://nominatim.org/) depending on token availability
 * and API status, and includes built-in sequential queue throttling for OSM requests to avoid getting banned from the API.
 */
export class Geolocation {
    static OSM_COORDINATE_FETCH_DELAY = 1000;

    constructor() {
        this.http = useService("http");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this._mapBoxToken = session.map_box_token || "";
        this._osmQueue = [];
        this._isProcessingQueue = false;
        this._waitProm = Promise.resolve();

        this.useMapBoxAPI = !!this._mapBoxToken;
        this.allowFetchOSM = true;
    }

    get mapBoxToken() {
        return this._mapBoxToken;
    }

    /**
     * Fetches coordinates of an address using MapBox if enabled, and falls back to OpenStreetMap otherwise or in case of error.
     *
     * @param {string} address
     * @returns {Promise<Array<{address: string, latitude: number, longitude: number}>>} Promise of list of Objects ordered by relevance. Values closer to 1 mean closer match to the input
     */
    async searchCoordinatesFromAddress(address) {
        if (this.useMapBoxAPI) {
            return this._fetchCoordinatesFromAddressMB(address);
        }
        const { promise, resolve } = Promise.withResolvers();
        this._osmQueue.push(() => this._fetchCoordinatesFromAddressOSM(address).then(resolve));
        this._processOSMQueue();
        return promise;
    }
    /**
     * Fetches the address of coordinates using MapBox if enabled, and falls back to OpenStreetMap otherwise or in case of error.
     *
     * @param {number} lat latitude
     * @param {number} lon longitude
     * @returns {Promise<{street: string, house_number: string, city: string, zip: string, state: string, country: string}>} Promise containing the fetched address Object
     */
    async searchAddressFromCoordinates(lat, lon) {
        if (this.useMapBoxAPI) {
            return this._fetchAddressFromCoordinatesMB(lat, lon);
        }
        const { promise, resolve } = Promise.withResolvers();
        this._osmQueue.push(() => this._fetchAddressFromCoordinatesOSM(lat, lon).then(resolve));
        this._processOSMQueue();
        return promise;
    }
    /**
     * Geolocates partners (i.e., finding their coordinates) based on their address.
     *
     * @param {Array<{contact_address_complete: string, partner_latitude: number, partner_longitude: number}>} partners
     * @param {Function|undefined} onPartnerGeolocated optional callback to be executed every time a partner is geolocated
     * @returns {Promise<void>} Resolves when all partners have been geolocated and results written in db
     */
    async geolocatePartners(partners, onPartnerGeolocated) {
        if (!Array.isArray(partners)) {
            partners = [partners];
        }
        // Group partners by address to reduce address list
        const addressPartnerMap = new Map();
        for (const partner of partners) {
            if (!hasValidCoordinates(partner)) {
                partner.partner_latitude = undefined;
                partner.partner_longitude = undefined;
                if (!partner.contact_address_complete) {
                    onPartnerGeolocated?.();
                }
            }
            if (
                partner.contact_address_complete &&
                (!partner.partner_latitude || !partner.partner_longitude)
            ) {
                if (!addressPartnerMap.has(partner.contact_address_complete)) {
                    addressPartnerMap.set(partner.contact_address_complete, []);
                }
                addressPartnerMap.get(partner.contact_address_complete).push(partner);
            }
        }
        if (addressPartnerMap.size === 0) {
            return;
        }

        const partnersToCache = [];
        const promises = [...addressPartnerMap].map(async ([address, partners]) => {
            const coordinates = await this.searchCoordinatesFromAddress(address);
            if (coordinates.length) {
                for (const partner of partners) {
                    partner.partner_longitude = coordinates[0].longitude;
                    partner.partner_latitude = coordinates[0].latitude;
                    partnersToCache.push(partner);
                }
            }
            onPartnerGeolocated?.();
        });
        await Promise.all(promises);
        this._writePartnersLatitudeLongitude(partnersToCache);
    }
    /**
     * Fetches the route using a list of coordinates as waypoints using the MapBox API, if enabled.
     *
     * @param {Array<{latitude: number, longitude: number}>} coordinates List of waypoints.
     * @param {String} routing The routing profile:
     *      - Disabled: No routing is calculated nor displayed.
     *      - Optimized: Computes the route for minimal travel time between records (the current default behavior).
     *      - Ordered: Routes strictly follow the default order set on the view.
     * @returns {Promise<Route>} Promise resolving to a route object, containing the following:
     *      - Route.geometry.legs[i]: contains one leg (i.e: the trip between two markers).
     *      - Route.geometry.legs[i].steps: contains the sets of coordinates to follow to reach a point from an other.
     *      - Route.geometry.legs[i].distance: the distance in meters to reach the destination
     *      - Route.geometry.legs[i].duration: the duration in seconds of the leg
     *      - Route.geometry.coordinates: contains the sets of coordinates to go from the first to the last marker without the notion of waypoint
     */
    async fetchRoute(coordinates, routing = "optimized") {
        if (!this.useMapBoxAPI || routing === "disabled" || coordinates.length < 2) {
            return null;
        }
        // The optimization API accepts fewer coordinates than the directions API.
        const maxCoordinates = routing === "optimized" ? 12 : 25;
        if (coordinates.length > maxCoordinates) {
            this.notification.add(_t("Routing is limited to %s addresses", maxCoordinates), {
                type: "warning",
            });
            return null;
        }
        const waypoints = coordinates
            .map(({ latitude, longitude }) => `${longitude},${latitude}`)
            .join(";");
        const token = this._mapBoxToken;
        const encodedUrl =
            routing === "optimized"
                ? `https://api.mapbox.com/optimized-trips/v1/mapbox/driving/${waypoints}?access_token=${token}&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last`
                : `https://api.mapbox.com/directions/v5/mapbox/driving/${waypoints}?access_token=${token}&steps=true&geometries=geojson`;
        const res = await this.http
            .get(encodedUrl)
            .catch((error) => this._mapBoxErrorHandling(error));
        if (!res) {
            return null;
        }
        if (res.message) {
            this.notification.add(_t(res.message), { type: "warning" });
            return null;
        }
        return routing === "optimized" ? res.trips[0] : res.routes[0]; // [0] because we don't use alternatives
    }
    /**
     * Tells the service to stop fetching coordinates.
     * In openStreetMap mode, the service starts to fetch coordinates once every second.
     * This fetching has to be done every second if we don't want to be banned from openStreetMap.
     * There are typically two cases when we need to stop fetching:
     * - when component is about to be unmounted because the request is bound to
     *   the component and it will crash if we do so.
     * - when calling the `load` method as it will start fetching new coordinates.
     */
    stopFetchingCoordinates() {
        this._osmQueue = [];
        this._isProcessingQueue = false;
    }

    //----------------------------------------------------------------------
    // Private
    //----------------------------------------------------------------------

    /**
     * OpenStreetMap only allows one request per second so we ensure to wait 1 second between each request.
     * @private
     */
    async _processOSMQueue() {
        if (this._isProcessingQueue) {
            return;
        }
        this._isProcessingQueue = true;
        let request;
        while ((request = this._osmQueue.shift())) {
            await this._waitProm;
            this._waitProm = delay(this.constructor.OSM_COORDINATE_FETCH_DELAY);
            request();
        }
        this._isProcessingQueue = false;
    }
    /**
     * @private
     */
    async _writePartnersLatitudeLongitude(partners) {
        partners = partners.filter(hasValidCoordinates);
        if (partners.length) {
            await this.orm.unscoped.call("res.partner", "update_latitude_longitude", [partners]);
        }
    }
    /**
     * Converts the addresses to coordinates using the mapbox API.
     *
     * @private
     * @param {String} address
     * @returns {Promise<Array<Object>>} promise resolving to an array of addresses and coordinates, ordered by descending relevance
     */
    async _fetchCoordinatesFromAddressMB(address) {
        const token = this._mapBoxToken;
        if (!token) {
            return [];
        }
        const encodedAddress = encodeURIComponent(address.replace("/", " "));
        const encodedUrl = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodedAddress}.json?access_token=${token}&cachebuster=1552314159970&autocomplete=true`;
        const res = await this.http
            .get(encodedUrl)
            .catch((error) => this._mapBoxErrorHandling(error));
        if (!res?.features.length) {
            return [];
        }
        return res.features.map((f) => ({
            address: f.place_name,
            longitude: parseFloat(f.geometry.coordinates[0]),
            latitude: parseFloat(f.geometry.coordinates[1]),
        }));
    }
    /**
     * Converts the addresses to coordinates using the openStreetMap API.
     *
     * @private
     * @param {String} address
     * @returns {Promise<Array<Object>>} promise resolving to an array of addresses and coordinates, ordered by descending relevance
     */
    async _fetchCoordinatesFromAddressOSM(address) {
        if (!this.allowFetchOSM) {
            return [];
        }
        const encodedAddress = encodeURIComponent(address.replace("/", " "));
        const encodedUrl = `https://nominatim.openstreetmap.org/search?q=${encodedAddress}&format=jsonv2`;
        const res = await this.http.get(encodedUrl).catch(() => this._osmErrorHandling());
        if (!res?.length) {
            return [];
        }
        return res.map((r) => ({
            address: r.display_name,
            longitude: parseFloat(r.lon),
            latitude: parseFloat(r.lat),
        }));
    }
    /**
     * Converts the coordinates to addresses using the mapbox API.
     *
     * @private
     * @param {number} lat latitude
     * @param {number} lon longitude
     * @returns {Promise<Address>} promise resolving to an address object
     */
    async _fetchAddressFromCoordinatesMB(lat, lon) {
        const token = this._mapBoxToken;
        if (!token) {
            return {};
        }
        const encodedUrl = `https://api.mapbox.com/geocoding/v5/mapbox.places/${lon},${lat}.json?access_token=${token}&cachebuster=1552314159970&types=address,place,postcode,region,country`;
        const res = await this.http
            .get(encodedUrl)
            .catch((error) => this._mapBoxErrorHandling(error));
        if (!res?.features?.length) {
            return {};
        }
        const getFeature = (type) =>
            res.features.find((feature) => feature.place_type.includes(type));
        return {
            street: getFeature("address")?.text,
            house_number: getFeature("address")?.address,
            city: getFeature("place")?.text,
            zip: getFeature("postcode")?.text,
            state: getFeature("region")?.text,
            country: getFeature("country")?.text,
        };
    }
    /**
     * Converts the coordinates to addresses using the openStreetMap API.
     *
     * @private
     * @param {number} lat latitude
     * @param {number} lon longitude
     * @returns {Promise<Object>} promise resolving to an address object
     */
    async _fetchAddressFromCoordinatesOSM(lat, lon) {
        if (!this.allowFetchOSM) {
            return {};
        }
        const encodedUrl = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=jsonv2`;
        const res = await this.http.get(encodedUrl).catch(() => this._osmErrorHandling());
        if (!res?.address) {
            return {};
        }
        return {
            street: res.address.road,
            house_number: res.address.house_number,
            city: res.address.city,
            zip: res.address.postcode,
            state: res.address.state,
            country: res.address.country,
        };
    }
    /**
     * Handles the displaying of error message according to the error.
     *
     * @private
     * @param {Object} error contains the error returned by the requests
     * @param {number} error.status contains the `status_code` of the failed http request
     */
    _mapBoxErrorHandling(error) {
        switch (error.status) {
            case 401:
                this.useMapBoxAPI = false;
                this.notification.add(
                    _t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: _t("Token invalid"),
                        type: "danger",
                    }
                );
                break;
            case 403:
                this.useMapBoxAPI = false;
                this.notification.add(
                    _t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: _t("Unauthorized connection"),
                        type: "danger",
                    }
                );
                break;
            case 422: // Max. addresses reached
            case 429: // Max. requests reached
                this.notification.add(MB_ERROR_MESSAGES[error.responseJSON.message], {
                    type: "warning",
                });
                break;
            case 500:
                this.useMapBoxAPI = false;
                this.notification.add(
                    _t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: _t("MapBox servers unreachable"),
                        type: "danger",
                    }
                );
        }
    }
    /**
     * Handles the displaying of error message according to the error.
     *
     * @private
     */
    _osmErrorHandling() {
        this.allowFetchOSM = false;
        this.notification.add(_t("OpenStreetMap's request limit exceeded, try again later."), {
            type: "danger",
        });
    }
}
