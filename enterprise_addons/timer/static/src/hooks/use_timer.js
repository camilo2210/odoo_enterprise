import { useService } from "@web/core/utils/hooks";

export function useTimer() {
    const timerService = useService("timer");
    const timerReactive = timerService.createTimer();

    return timerReactive;
}
