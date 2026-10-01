/** @odoo-module default=false **/
export const COLORS = [
    "#FFFFFF",
    "#262c34",
    "#f1c40f",
    "#FBB130",
    "#FC787D",
    "#EB5A46",
    "#9b59b6",
    "#0079BF",
    "#1BB6F9",
    "#4dd0e1",
    "#00CEB3",
    "#2ecc71",
];

export const BG_COLORS = [
    "#FFFFFF",
    "#1abc9c",
    "#58a177",
    "#B4C259",
    "#56829f",
    "#636DA9",
    "#34495e",
    "#BC4242",
    "#C6572A",
    "#d49054",
    "#D89F45",
    "#DAB852",
    "#606060",
    "#6B6C70",
    "#838383",
];

/**
 * @param {Integer} string_length
 * @returns {String} A random string with numbers and lower/upper case chars
 */
export function randomString(string_length) {
    var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    var randomstring = "";
    for (var i = 0; i < string_length; i++) {
        var rnum = Math.floor(Math.random() * chars.length);
        randomstring += chars.substring(rnum, rnum + 1);
    }
    return randomstring;
}

export default {
    BG_COLORS,
    COLORS,
    randomString,
};
