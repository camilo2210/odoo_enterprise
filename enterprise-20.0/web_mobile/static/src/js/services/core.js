/* global OdooDeviceUtility */
/* global OdooDevicePolyfill */

import { uniqueId } from "@web/core/utils/functions";
import { location, browser } from "@web/core/browser/browser";
import { parseSearchQuery } from "@web/core/browser/router";
import { patch } from "@web/core/utils/patch";
import { BackButtonManager } from "@web/core/utils/hooks";

const available = typeof OdooDeviceUtility !== "undefined";
let DeviceUtility;
const deferreds = {};
export const methods = {};

if (available) {
    DeviceUtility = OdooDeviceUtility;
    delete window.OdooDeviceUtility;
}

/**
 * Responsible for invoking native methods which called from JavaScript
 *
 * @param {String} name name of action want to perform in mobile
 * @param {Object} args extra arguments for mobile
 *
 * @returns Promise Object
 */
function native_invoke(name, args) {
    if (args === undefined) {
        args = {};
    }
    const id = uniqueId();
    args = JSON.stringify(args);
    DeviceUtility.execute(name, args, id);
    return new Promise(function (resolve, reject) {
        deferreds[id] = {
            successCallback: resolve,
            errorCallback: reject,
        };
    });
}

/**
 * Manages deferred callback from initiate from native mobile
 *
 * @param {String} id callback id
 * @param {Object} result
 */
window.odoo.native_notify = function (id, result) {
    if (Object.prototype.hasOwnProperty.call(deferreds, id)) {
        if (result.success) {
            deferreds[id].successCallback(result);
        } else {
            deferreds[id].errorCallback(result);
        }
    }
};

const plugins = available ? JSON.parse(DeviceUtility.list_plugins()) : [];
plugins.forEach((plugin) => {
    methods[plugin.name] = function (args) {
        return native_invoke(plugin.action, args);
    };
});

let polyfills = {};

if (window.OdooDevicePolyfill) {
    polyfills = OdooDevicePolyfill;
}

/**
 * Use to notify an uri hash change on native devices (ios / android)
 */
if (methods.hashChange) {
    let currentSearch;
    browser.addEventListener("popstate", function () {
        const search = parseSearchQuery(location.search);
        if (JSON.stringify(currentSearch) !== JSON.stringify(search)) {
            methods.hashChange(search);
        }
        currentSearch = search;
    });
}

patch(BackButtonManager.prototype, {
    _activate() {
        if (methods.overrideBackButton) {
            document.addEventListener("backbutton", this._boundPerformLatestBackAction);
            methods.overrideBackButton({ enabled: true });
        } else {
            super._activate();
        }
    },
    _deactivate() {
        if (methods.overrideBackButton) {
            document.removeEventListener("backbutton", this._boundPerformLatestBackAction);
            methods.overrideBackButton({ enabled: false });
        } else {
            super._deactivate();
        }
    },
});

export default {
    methods,
    polyfills,
};
