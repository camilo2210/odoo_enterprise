export class AIChannelDataRegistry {
    constructor() {
        this.data = {};
    }

    setData(channelId, key, value) {
        this.data[channelId] = this.data[channelId] || {};
        this.data[channelId][key] = value;
    }
    getData(channelId, key) {
        return this.data[channelId][key];
    }
    removeData(channelId) {
        delete this.data[channelId];
    }
}

export const aiChannelDataRegistry = new AIChannelDataRegistry();
