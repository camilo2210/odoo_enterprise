import { registry } from "@web/core/registry";
import { TimerReactive } from "../models/timer_reactive";

export const timerService = {
    start(env) {
        let timer;
        return {
            get timer() {
                return timer;
            },
            createTimer() {
                if (!timer) {
                    timer = new TimerReactive(env);
                }
                return timer;
            },
        };
    },
};

registry.category("services").add("timer", timerService);
