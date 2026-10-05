import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";

export const ODOO_COLOR = "#714B67";
export const SUCCESS_COLOR = "#00FF00";
export const SUCCESS_ANIMATION = "snake";

const hasLeds = () => hasMobileNative("setLedAnimation");

export function registerSuccessAnimation() {
    if (!hasLeds()) {
        return;
    }
    fireAndForget(() =>
        mobileNative.setLedAnimation({
            preset: SUCCESS_ANIMATION,
            color: SUCCESS_COLOR,
            durationMs: 40,
            loop: 0,
            play: false,
        })
    );
}

export function setCompanyColor(config) {
    if (hasLeds()) {
        const color = config.self_ordering_primary_color ?? ODOO_COLOR;
        fireAndForget(() => mobileNative.setLedDefaultColor({ color }));
    }
}

export function playSuccessAnimation() {
    if (hasLeds()) {
        fireAndForget(() =>
            mobileNative.playLedAnimation({
                preset: SUCCESS_ANIMATION,
                durationMs: 3000,
                restoreColor: SUCCESS_COLOR,
            })
        );
    }
}

function fireAndForget(call) {
    Promise.resolve(call()).catch((e) => {
        console.error("Failed to call the kiosk LED API", e);
    });
}
