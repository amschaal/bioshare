// url-state.js — read/write nested state to window.location.search.
//
// Mirrors the flatten/unflatten encoding used by the old AngularJS
// ngPageState.LocationSearchState so existing bookmarks keep working:
//   { tableSettings: { page: 2, sorting: { updated: 'desc' } }, cols: { Share: true } }
//       <->  ?tableSettings.page=2&tableSettings.sorting.updated=desc&cols.Share=true

function flatten(data) {
    const result = {};
    function recurse(cur, prop) {
        if (Object(cur) !== cur) {
            result[prop] = cur;
        } else if (Array.isArray(cur)) {
            for (let i = 0, l = cur.length; i < l; i++) {
                recurse(cur[i], `${prop}[${i}]`);
            }
            if (cur.length === 0) result[prop] = [];
        } else {
            let isEmpty = true;
            for (const p in cur) {
                isEmpty = false;
                recurse(cur[p], prop ? `${prop}.${p}` : p);
            }
            if (isEmpty && prop) result[prop] = {};
        }
    }
    recurse(data, '');
    return result;
}

function unflatten(data) {
    if (Object(data) !== data || Array.isArray(data)) return data;
    const regex = /\.?([^.\[\]]+)|\[(\d+)\]/g;
    const resultholder = {};
    for (const p in data) {
        let cur = resultholder;
        let prop = '';
        let m;
        while ((m = regex.exec(p)) !== null) {
            cur = cur[prop] || (cur[prop] = (m[2] ? [] : {}));
            prop = m[2] || m[1];
        }
        cur[prop] = data[p];
    }
    return resultholder[''] || resultholder;
}

/**
 * Read the current URL search params into a nested object.
 */
export function getUrlState() {
    const params = new URLSearchParams(window.location.search);
    const flat = {};
    for (const [k, v] of params) flat[k] = v;
    return unflatten(flat);
}

/**
 * Replace the URL search params with the flattened form of `data`.
 * Uses history.replaceState so it does not add a history entry.
 */
export function setUrlState(data) {
    const flat = flatten(data);
    const params = new URLSearchParams();
    for (const k of Object.keys(flat)) {
        if (flat[k] === undefined || flat[k] === null || flat[k] === '') continue;
        params.set(k, flat[k]);
    }
    const qs = params.toString();
    const url = `${window.location.pathname}${qs ? '?' + qs : ''}${window.location.hash}`;
    window.history.replaceState(window.history.state, '', url);
}

/**
 * Merge a partial state object into the existing URL state.
 */
export function mergeUrlState(partial) {
    setUrlState({ ...getUrlState(), ...partial });
}
