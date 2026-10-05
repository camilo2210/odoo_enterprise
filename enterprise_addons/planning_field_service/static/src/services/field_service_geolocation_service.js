import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

export class FieldServiceGeolocationService {
    constructor({ services }) {
        this.orm = services["orm"];
        this.notification = services["notification"];
        this.watchId = null;
        this.currentPosition = {};
    }

    async isFeatureEnabled() {
        const [isGeolocationEnabled, isPlanningUser] = await Promise.all([
            user.hasGroup("planning.group_field_service_allow_geolocation"),
            user.hasGroup("planning.group_planning_user"),
        ]);
        return isGeolocationEnabled && isPlanningUser;
    }

    get isWatchRunning() {
        return !!this.watchId;
    }

    async startWatch() {
        const isFeatureEnabled = await this.isFeatureEnabled();
        if (!isFeatureEnabled || !navigator.geolocation || this.isWatchRunning) {
            return;
        }
        this.watchId = navigator.geolocation.watchPosition(
            async ({ coords: { latitude, longitude } }) => {
                this.currentPosition = {
                    latitude: latitude,
                    longitude: longitude,
                };
                const keepTracking = await this.orm.call(
                    "res.users",
                    "update_resource_live_location",
                    [latitude, longitude]
                );
                if (!keepTracking) {
                    await this.stopWatch(true);
                }
            },
            async () => {
                await this.stopWatch(true);
            },
            { enableHighAccuracy: true, maximumAge: 10000 }
        );
    }

    async stopWatch(eraseLocation) {
        if (!this.isWatchRunning) {
            return;
        }
        if (eraseLocation === undefined) {
            eraseLocation = await this.orm.call("res.users", "should_erase_live_location");
        }
        navigator.geolocation.clearWatch(this.watchId);
        this.watchId = null;
        if (eraseLocation) {
            await this.orm.call("res.users", "erase_resource_live_location");
            this.currentPosition = {};
        }
    }

    async _getPosition() {
        return new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
            });
        });
    }

    async getGeolocation() {
        const isFeatureEnabled = await this.isFeatureEnabled();
        if (!isFeatureEnabled) {
            return false;
        }
        if (Object.keys(this.currentPosition).length > 0) {
            return {
                success: true,
                ...this.currentPosition,
            };
        }
        try {
            const position = await this._getPosition();
            return {
                success: true,
                longitude: position.coords.longitude,
                latitude: position.coords.latitude,
            };
        } catch (err) {
            return {
                success: false,
                message: _t("Location error: %s", err.message),
            };
        }
    }
}

export const fieldServiceGeolocationService = {
    dependencies: ["orm", "notification"],
    async start(env, services) {
        return new FieldServiceGeolocationService(env, services);
    },
};

registry.category("services").add("field_service_geolocation", fieldServiceGeolocationService);
