import { Reactive } from "@web/core/utils/reactive";
const { DateTime, Interval } = luxon;

export class TimerReactive extends Reactive {
    constructor(env) {
        super();
        this.resetTimer();
    }

    get toSeconds() {
        return (this.hours * 60 + this.minutes) * 60 + this.seconds;
    }

    get floatValue() {
        return this.toSeconds / 3600;
    }

    formatTime() {
        const hours = `${this.hours}`.padStart(2, "0");
        const minutes = `${this.minutes}`.padStart(2, "0");
        const seconds = `${this.seconds}`.padStart(2, "0");
        this.time = `${hours}:${minutes}:${seconds}`;
    }

    addHours(hours) {
        this.hours += hours;
    }

    addMinutes(minutes) {
        minutes += this.minutes;
        this.minutes = minutes % 60;
        this.addHours(Math.floor(minutes / 60));
    }

    addSeconds(seconds) {
        seconds += this.seconds;
        this.seconds = seconds % 60;
        this.addMinutes(Math.floor(seconds / 60));
    }

    setTimer(timeElapsed, timerStart) {
        this.resetTimer();
        this.addFloatTime(timeElapsed);
        this.timeElapsed = this.toSeconds;

        if (timerStart) {
            const { hours, minutes, seconds } = this.getInterval(timerStart, this.getCurrentTime())
                .toDuration(["hours", "minutes", "seconds", "milliseconds"])
                .toObject();
            this.addHours(hours);
            this.addMinutes(minutes);
            this.addSeconds(seconds);
        }
    }

    getInterval(dateA, dateB) {
        const [startDate, endDate] = dateA <= dateB ? [dateA, dateB] : [dateB, dateA];
        return Interval.fromDateTimes(startDate, endDate);
    }

    getCurrentTime() {
        return DateTime.now();
    }

    addFloatTime(timeElapsed) {
        if (timeElapsed === 0) {
            this.hours = this.minutes = this.seconds = 0;
            return;
        }

        const minutes = timeElapsed % 1;
        this.hours = timeElapsed - minutes;
        this.minutes = minutes * 60;
    }

    updateTimer(timerStart) {
        const currentTime = this.getCurrentTime();
        const timeElapsed = this.getInterval(timerStart, currentTime);
        const { seconds } = timeElapsed.toDuration(["seconds", "milliseconds"]).toObject();
        this.addSeconds(seconds - this.toSeconds + this.timeElapsed);
    }

    resetTimer() {
        this.hours = 0;
        this.minutes = 0;
        this.seconds = 0;
        this.timeElapsed = 0;
        this.time = "";
    }
}
