/** @odoo-module ignore **/

class AiScriptsManager {
    constructor() {
        this.observerEntries = new Set();
    }

    // Run `fn(...args)`. Overridden by the builder to run the call inside the
    // editor's mutation-ignoring scope, so AI mutations stay out of history.
    runCallback(fn, args) {
        return fn(...args);
    }

    /**
     * Wrap a callback so the mutations it makes are attributed to AI code.
     *
     * @param {Function} fn
     * @returns {Function}
     */
    protectMutations(fn, scriptEl) {
        return (...args) => {
            try {
                this.flushObservers(false);
                return this.runCallback(fn, args, { scriptEl });
            } finally {
                // Changes done in this microtick are made by an AI script.
                this.flushObservers(true);
            }
        };
    }

    whenReady(fn, scriptEl) {
        const run = this.protectMutations(fn, scriptEl);
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", run, { once: true });
        } else {
            run();
        }
    }

    /**
     * @param {boolean} aiChanges - whether queued mutations were made by an AI
     * script.
     */
    flushObservers(aiChanges) {
        // Flush all tracked observers, so pending mutations are correctly
        // marked.
        for (const { observer, handleRecords } of this.observerEntries) {
            const records = observer.takeRecords();
            if (records.length) {
                handleRecords(records, aiChanges);
            }
        }
    }

    // AI uses next functions in its script to track mutations, however they are
    // needed only for people with the editor access, so we define dummy
    // placeholders here, and replace them for the real ones in
    // `ai_script_tracking`.
    trackElement() {}
    registerCleanup() {}
}

const manager = new AiScriptsManager();

function getApi(scriptEl) {
    return Object.freeze({
        protectMutations: (fn) => manager.protectMutations(fn, scriptEl),
        trackElement: (element) => manager.trackElement(element, scriptEl),
        registerCleanup: (cleanupFn) => manager.registerCleanup(cleanupFn, scriptEl),
        whenReady: (fn) => manager.whenReady(fn, scriptEl),
    });
}

window.__aiScriptsManager__ = { getApi, manager };
