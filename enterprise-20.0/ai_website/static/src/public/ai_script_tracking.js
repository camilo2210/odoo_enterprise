/** @odoo-module ignore **/

// Only served to users who can open the builder.

const trackedElementsMap = new Map();
const scriptElementsMap = new Map();
const scriptCleanupMap = new Map();

// A single observer watches every tracked element, so that `protectMutations`
// flushes the whole page with one `takeRecords()`.
let observerEntry = null;

/**
 * @param {AiScriptsManager} manager
 * @returns {{observer: MutationObserver, handleRecords: Function}}
 */
function getObserverEntry(manager) {
    if (!observerEntry) {
        const handleRecords = (mutations, isAIChange) => {
            for (const mutation of mutations) {
                trackedElementsMap.get(mutation.target)?.handleRecord(mutation, isAIChange);
            }
        };
        observerEntry = {
            observer: new MutationObserver((records) => handleRecords(records, false)),
            handleRecords,
        };
        manager.observerEntries.add(observerEntry);
    }
    return observerEntry;
}

/**
 * @param {AiScriptsManager} manager
 */
function stopObserving(manager) {
    if (observerEntry) {
        observerEntry.observer.disconnect();
        manager.observerEntries.delete(observerEntry);
        observerEntry = null;
    }
}

function runScriptCleanup(scriptEl) {
    try {
        const cleanupFn = scriptCleanupMap.get(scriptEl);
        if (cleanupFn) {
            cleanupFn();
        }
    } catch (error) {
        console.warn("AI script cleanup failed:", error);
    }
}

let styleParserEl = null;

/**
 * Parse a style attribute string into a Map of property -> {value, priority}.
 *
 * @param {string|null} styleStr
 * @returns {Map<string, {value: string, priority: string}>}
 */
function parseStyleMap(styleStr) {
    const map = new Map();
    if (!styleStr) {
        return map;
    }
    // Reused across calls: this runs on every style mutation of every tracked
    // element, i.e. once per frame per element for an animated one.
    styleParserEl ||= document.createElement("div");
    styleParserEl.style.cssText = styleStr;
    for (let i = 0; i < styleParserEl.style.length; i++) {
        const prop = styleParserEl.style[i];
        map.set(prop, {
            value: styleParserEl.style.getPropertyValue(prop),
            priority: styleParserEl.style.getPropertyPriority(prop),
        });
    }
    return map;
}

function parseClassSet(classStr) {
    return new Set((classStr || "").split(/\s+/).filter(Boolean));
}

Object.assign(window.__aiScriptsManager__.manager, {
    trackElement(element, scriptEl) {
        if (!element) {
            return;
        }
        // Several scripts may mutate the same element.
        if (scriptEl) {
            if (!scriptElementsMap.has(scriptEl)) {
                scriptElementsMap.set(scriptEl, new Set());
            }
            scriptElementsMap.get(scriptEl).add(element);
        }
        if (trackedElementsMap.has(element)) {
            return;
        }
        element.dataset.aiTracked = "true";

        // Per-property AI ownership tracking.
        // Each map stores property -> original value before AI touched it.
        // A `null` value means the property did not exist before AI added it.
        // `class` instead stores className -> whether AI added it,`true` must
        // be removed, `false` was removed by AI and must be added back.
        const aiElementModifications = {
            attr: new Map(),
            style: new Map(),
            class: new Map(),
        };

        const handleRecord = (mutation, isAIChange) => {
            const attr = mutation.attributeName;

            if (isAIChange) {
                if (attr === "style") {
                    const oldStyles = parseStyleMap(mutation.oldValue);
                    // Properties AI code added or changed.
                    for (let i = 0; i < element.style.length; i++) {
                        const prop = element.style[i];
                        const oldEntry = oldStyles.get(prop);
                        const newVal = element.style.getPropertyValue(prop);
                        if (!oldEntry || oldEntry.value !== newVal) {
                            // Only record the first pre-AI value.
                            if (!aiElementModifications.style.has(prop)) {
                                aiElementModifications.style.set(prop, oldEntry ?? null);
                            }
                        }
                    }
                    // Properties AI code removed.
                    for (const [prop, entry] of oldStyles) {
                        if (
                            !element.style.getPropertyValue(prop) &&
                            !aiElementModifications.style.has(prop)
                        ) {
                            aiElementModifications.style.set(prop, entry);
                        }
                    }
                } else if (attr === "class") {
                    const oldClasses = parseClassSet(mutation.oldValue);
                    for (const cls of element.classList) {
                        if (!oldClasses.has(cls) && !aiElementModifications.class.has(cls)) {
                            aiElementModifications.class.set(cls, true);
                        }
                    }
                    for (const cls of oldClasses) {
                        if (
                            !element.classList.contains(cls) &&
                            !aiElementModifications.class.has(cls)
                        ) {
                            aiElementModifications.class.set(cls, false);
                        }
                    }
                } else {
                    if (!aiElementModifications.attr.has(attr)) {
                        aiElementModifications.attr.set(attr, mutation.oldValue);
                    }
                }
            } else {
                if (attr === "style") {
                    const oldStyles = parseStyleMap(mutation.oldValue);
                    // Properties changed by non-AI code.
                    for (let i = 0; i < element.style.length; i++) {
                        const prop = element.style[i];
                        const oldEntry = oldStyles.get(prop);
                        if (!oldEntry || oldEntry.value !== element.style.getPropertyValue(prop)) {
                            aiElementModifications.style.delete(prop);
                        }
                    }
                    // Properties removed by non-AI code.
                    for (const [prop] of oldStyles) {
                        if (!element.style.getPropertyValue(prop)) {
                            aiElementModifications.style.delete(prop);
                        }
                    }
                } else if (attr === "class") {
                    const oldClasses = parseClassSet(mutation.oldValue);
                    // Classes added by non-AI code.
                    for (const cls of element.classList) {
                        if (!oldClasses.has(cls)) {
                            aiElementModifications.class.delete(cls);
                        }
                    }
                    // Classes removed by non-AI code.
                    for (const cls of oldClasses) {
                        if (!element.classList.contains(cls)) {
                            aiElementModifications.class.delete(cls);
                        }
                    }
                } else {
                    aiElementModifications.attr.delete(attr);
                }
            }
        };

        trackedElementsMap.set(element, { aiElementModifications, handleRecord });
        getObserverEntry(this).observer.observe(element, {
            attributes: true,
            attributeOldValue: true,
        });
    },

    restoreElement(targetEl) {
        const entry = trackedElementsMap.get(targetEl);
        if (entry) {
            const { aiElementModifications } = entry;
            // Untrack before reverting, so that the records the revert itself
            // produces are ignored.
            trackedElementsMap.delete(targetEl);
            if (!trackedElementsMap.size) {
                stopObserving(this);
            }

            // Revert AI-overridden style properties.
            for (const [prop, original] of aiElementModifications.style) {
                if (original === null) {
                    targetEl.style.removeProperty(prop);
                } else {
                    targetEl.style.setProperty(prop, original.value, original.priority);
                }
            }

            // Revert AI-overridden classes: drop the ones it added, restore the ones it removed.
            for (const [cls, wasAdded] of aiElementModifications.class) {
                targetEl.classList.toggle(cls, !wasAdded);
            }

            // Revert AI-overridden attributes.
            for (const [attr, originalVal] of aiElementModifications.attr) {
                if (originalVal === null) {
                    targetEl.removeAttribute(attr);
                } else {
                    targetEl.setAttribute(attr, originalVal);
                }
            }
        }
        delete targetEl.dataset.aiTracked;
    },

    registerCleanup(cleanupFn, scriptEl) {
        scriptCleanupMap.set(scriptEl, cleanupFn);
    },

    disposeScript(scriptEl) {
        runScriptCleanup(scriptEl);
        const elements = scriptElementsMap.get(scriptEl);
        if (elements) {
            elements.forEach((el) => this.restoreElement(el));
            scriptElementsMap.delete(scriptEl);
        }
    },

    disposeAll() {
        document.querySelectorAll("script[data-ai-script-id]").forEach(runScriptCleanup);
        for (const element of [...trackedElementsMap.keys()]) {
            this.restoreElement(element);
        }
        stopObserving(this);
        this.observerEntries.clear();
        scriptElementsMap.clear();
    },
});
