export const fakeSignInfoService = (signInfo) => ({
    get(key) {
        return signInfo[key];
    },
    set(data) {
        Object.assign(signInfo, data);
    },
});
