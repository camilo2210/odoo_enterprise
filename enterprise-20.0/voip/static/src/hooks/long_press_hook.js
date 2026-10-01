export const LONG_PRESS_DURATION = 400; // Duration in milliseconds for a long press

export function useLongPress(callback, delay = LONG_PRESS_DURATION) {
    let timer = null;
    let longPressTriggered = false;

    function cancel() {
        clearTimeout(timer);
    }

    return {
        get longPressTriggered() {
            return longPressTriggered;
        },
        onPointerDown(ev, params) {
            if (ev.button !== 0) {
                return;
            }
            longPressTriggered = false;
            timer = setTimeout(() => {
                longPressTriggered = true;
                callback(params);
            }, delay);
        },
        onPointerUp: cancel,
        onPointerCancel: cancel,
    };
}
