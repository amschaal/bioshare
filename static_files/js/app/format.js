// format.js — formatting helpers shared by Vue components and page orchestrators.

const KB = 1024;
const UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

/**
 * Format a byte count as a human-readable string.
 *   fmtBytes(0)         -> "0 B"
 *   fmtBytes(1500)      -> "1.5 KB"
 *   fmtBytes(2.5 * 1e9) -> "2.3 GB"
 */
export function fmtBytes(bytes) {
    if (bytes == null || isNaN(bytes)) return '';
    if (bytes === 0) return '0 B';
    const i = Math.min(Math.floor(Math.log(Math.abs(bytes)) / Math.log(KB)), UNITS.length - 1);
    const value = bytes / Math.pow(KB, i);
    return `${value.toFixed(value < 10 && i > 0 ? 1 : 0)} ${UNITS[i]}`;
}

/**
 * Format an ISO 8601 timestamp as a localized short date+time.
 *   fmtDateShort('2026-05-13T17:08:53Z') -> "5/13/26, 5:08 PM"  (en-US default)
 */
export function fmtDateShort(iso) {
    if (!iso) return '';
    const d = iso instanceof Date ? iso : new Date(iso);
    if (isNaN(d.getTime())) return '';
    return new Intl.DateTimeFormat(undefined, {
        year: '2-digit', month: 'numeric', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
    }).format(d);
}

/**
 * Format an ISO timestamp as a relative duration ("3 minutes ago").
 * Uses Intl.RelativeTimeFormat where available; falls back to fmtDateShort.
 */
export function fmtDateRelative(iso) {
    if (!iso) return '';
    const d = iso instanceof Date ? iso : new Date(iso);
    if (isNaN(d.getTime())) return '';
    if (typeof Intl.RelativeTimeFormat !== 'function') return fmtDateShort(iso);

    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
    const diffSec = Math.round((d.getTime() - Date.now()) / 1000);
    const abs = Math.abs(diffSec);
    if (abs < 60) return rtf.format(diffSec, 'second');
    if (abs < 3600) return rtf.format(Math.round(diffSec / 60), 'minute');
    if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), 'hour');
    if (abs < 2592000) return rtf.format(Math.round(diffSec / 86400), 'day');
    if (abs < 31536000) return rtf.format(Math.round(diffSec / 2592000), 'month');
    return rtf.format(Math.round(diffSec / 31536000), 'year');
}
