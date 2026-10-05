/** Shared state tracking whether the current AI turn (including any
 *  multi-step tool loop, e.g. create_page navigation) is still in progress. */
let pendingAiResponsePromise = null;

export function getAiResponsePromise() {
    return pendingAiResponsePromise;
}

export function setAiResponsePromise(promise) {
    pendingAiResponsePromise = promise;
    pendingAiResponsePromise.finally(() => {
        pendingAiResponsePromise = null;
    });
}
