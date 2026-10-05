export class RepeatedActionTipTracker {
    constructor(threshold = 3) {
        this.threshold = threshold;
        this.lastActionKey = null;
        this.streak = 0;
        this.dismissed = new Set();
    }

    registerAction(actionKey) {
        if (this.dismissed.has(actionKey)) {
            return false;
        }
        if (actionKey === this.lastActionKey) {
            this.streak += 1;
        } else {
            this.lastActionKey = actionKey;
            this.streak = 1;
        }
        if (this.streak >= this.threshold) {
            this.dismissed.add(actionKey);
            this.streak = 0;
            return true;
        }
        return false;
    }

    reset() {
        this.lastActionKey = null;
        this.streak = 0;
    }
}