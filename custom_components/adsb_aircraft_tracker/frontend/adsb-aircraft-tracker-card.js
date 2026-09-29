/*
 * ADSB Aircraft Tracker dashboard cards.
 *
 * Served and auto-loaded by the integration (see __init__.py), so every card
 * here shows up in the dashboard "Add card" picker with no resource setup:
 *
 *   custom:adsb-aircraft-tracker-card   nearest aircraft list with routes
 *   custom:adsb-closest-aircraft-card   the single closest aircraft, in detail
 *   custom:adsb-military-card           all-clear / military aircraft alert
 *   custom:adsb-stats-card              tracked count, closest, military, DB
 *
 * No card hardcodes entity ids. Each finds its tracker's entities through the
 * entity registry by platform + device + translation_key, so they work on old
 * installs (whatever ids they registered), new installs, renamed entities and
 * multiple feeders alike.
 */

const DOMAIN = "adsb_aircraft_tracker";

// translation_key -> role, plus an entity_id suffix fallback for registries
// that haven't picked up translation keys yet (pre-1.6.1 entities get them on
// their first load with 1.6.1, so this only matters very briefly).
const ROLES = {
  closest_aircraft: /_closest_aircraft$/,
  top_aircraft: /_nearest_\d+_aircraft$/,
  all_aircraft: /_all_aircraft$/,
  military_aircraft: /_military_aircraft_present$/,
  military_details: /_military_aircraft_details$/,
  military_database_status: /_military_database_status$/,
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (deg) => COMPASS[Math.round((((deg % 360) + 360) % 360) / 45) % 8];

// Best spoken/visible identity: callsign, then a real tail, then hex
const identOf = (a) =>
  a.flight || (a.tail && a.tail !== "Unknown" ? a.tail : null) || (a.hex ? a.hex.toUpperCase() : "Unknown");

const altBand = (a) => {
  const alt = Number(a.altitude_ft) || 0;
  if (a.on_ground || alt === 0) return "ground";
  return alt < 3000 ? "low" : alt < 10000 ? "mid" : "high";
};

function trackerEntities(hass, deviceId) {
  const found = {};
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform !== DOMAIN) continue;
    if (deviceId && entry.device_id !== deviceId) continue;
    for (const [role, suffix] of Object.entries(ROLES)) {
      if (found[role]) continue;
      if (entry.translation_key === role || (!entry.translation_key && suffix.test(entry.entity_id))) {
        found[role] = entry.entity_id;
      }
    }
  }
  return found;
}

function firstTrackerDevice(hass) {
  const entry = Object.values(hass.entities || {}).find(
    (e) => e.platform === DOMAIN && e.device_id
  );
  return entry ? entry.device_id : undefined;
}

const BASE_STYLE = `
  ha-card { overflow: hidden; }
  [data-entity] { cursor: pointer; }
  .header { display: flex; justify-content: space-between; align-items: baseline; padding: 16px 16px 8px; gap: 8px; }
  .title { font-size: 1.25em; font-weight: 500; }
  .muted { color: var(--secondary-text-color); }
  .empty { padding: 16px; color: var(--secondary-text-color); }
  ha-icon.high { color: var(--blue-color, #2196f3); }
  ha-icon.mid { color: var(--orange-color, #ff9800); }
  ha-icon.low { color: var(--deep-orange-color, #ff5722); }
  ha-icon.ground { color: var(--disabled-text-color); }
  .route { font-weight: 600; color: var(--primary-color); white-space: nowrap; }
`;

/** Shared plumbing: config, entity discovery, change detection, more-info. */
class AdsbBaseCard extends HTMLElement {
  // Roles whose state changes should re-render this card
  static watch = [];
  static defaultTitle = "Aircraft";
  static extraSchema = [];
  static extraLabels = {};

  setConfig(config) {
    this._config = { ...config };
    this._lastKey = undefined;
    this._registry = undefined;
    if (this._hass) this.hass = this._hass;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    // hass is set on every state change; only rescan the entity registry
    // when HA hands us a new registry object
    if (hass.entities !== this._registry) {
      this._registry = hass.entities;
      this._ids = trackerEntities(hass, this._config.device_id);
      this._lastKey = undefined;
    }
    // Re-render only when one of the entities this card shows changed
    const key = this.constructor.watch
      .map((role) => hass.states[this._ids[role]]?.last_updated).join("|");
    if (key === this._lastKey) return;
    this._lastKey = key;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  _state(role) {
    return this._hass.states[this._ids[role]];
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const title = this._config.title ?? this.constructor.defaultTitle;
    const found = this.constructor.watch.some((role) => this._ids[role]);
    const body = found
      ? this.renderBody(title)
      : `<ha-card header="${esc(title)}"><div class="empty">No ADSB Aircraft Tracker entities found${this._config.device_id ? " for the selected tracker" : ""}.</div></ha-card>`;
    this.shadowRoot.innerHTML = `${body}<style>${BASE_STYLE}${this.constructor.style || ""}</style>`;
    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (!el.dataset.entity) return;
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          detail: { entityId: el.dataset.entity }, bubbles: true, composed: true,
        }));
      });
    });
  }

  // Visual editor: which tracker, a title, plus any card-specific options
  static getConfigForm() {
    return {
      schema: [
        { name: "device_id", selector: { device: { integration: DOMAIN } } },
        ...this.extraSchema,
        { name: "title", selector: { text: {} } },
      ],
      computeLabel: (s) => ({ device_id: "Tracker", title: "Title", ...this.extraLabels })[s.name],
      computeHelper: (s) => (s.name === "device_id"
        ? "Leave empty to use the first ADSB tracker found." : undefined),
    };
  }

  static getStubConfig(hass) {
    return { device_id: firstTrackerDevice(hass) };
  }
}

/* ----- Nearest aircraft list ------------------------------------------ */

class AdsbAircraftTrackerCard extends AdsbBaseCard {
  static watch = ["top_aircraft", "all_aircraft", "military_aircraft"];
  static extraSchema = [
    { name: "count", default: 5, selector: { number: { min: 1, max: 5, mode: "slider" } } },
  ];
  static extraLabels = { count: "Aircraft to show" };
  static style = `
    .summary { display: flex; gap: 10px; align-items: center; color: var(--secondary-text-color); font-size: 0.9em; }
    .mil { display: inline-flex; align-items: center; gap: 4px; color: var(--error-color); font-weight: 600; }
    .mil ha-icon { --mdc-icon-size: 18px; }
    .row { display: flex; gap: 12px; align-items: center; padding: 8px 16px; }
    .row:hover { background: var(--secondary-background-color); }
    .row:last-child { padding-bottom: 14px; }
    .row ha-icon { flex: none; --mdc-icon-size: 22px; }
    .main { min-width: 0; flex: 1; }
    .line1 { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .ident { font-weight: 600; }
    .sub { color: var(--secondary-text-color); font-size: 0.85em; }
    .line1 .route { margin-left: auto; font-size: 0.85em; }
    .line2 { color: var(--secondary-text-color); font-size: 0.85em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  `;

  static getStubConfig(hass) {
    return { ...super.getStubConfig(hass), count: 5 };
  }

  getCardSize() {
    return 2 + Math.min(this._config?.count ?? 5, 5);
  }

  renderBody(title) {
    const top = this._state("top_aircraft");
    const all = this._state("all_aircraft");
    const count = Math.max(1, Math.min(Number(this._config.count) || 5, 5));
    const rows = [];
    for (let i = 1; i <= count; i++) {
      const a = top?.attributes?.[`aircraft_${i}`];
      if (!a) break;
      const ident = identOf(a);
      const sub = a.tail && a.tail !== "Unknown" && a.tail !== ident ? a.tail : "";
      const alt = Number(a.altitude_ft) || 0;
      const route = a.route_origin && a.route_destination
        ? `<span class="route" title="${esc(a.route_origin_name)} → ${esc(a.route_destination_name)}">${esc(a.route_origin)} → ${esc(a.route_destination)}</span>`
        : "";
      const facts = [
        a.distance_display,
        alt ? `${alt.toLocaleString()} ft` : null,
        a.speed_kts ? `${Math.round(a.speed_kts)} kts` : null,
      ].filter(Boolean).map(esc).join(" · ");
      const desc = a.description && a.description !== "Unknown aircraft" ? a.description : "";
      rows.push(`
        <div class="row" data-entity="${esc(this._ids.top_aircraft)}">
          <ha-icon class="${altBand(a)}" icon="mdi:airplane"></ha-icon>
          <div class="main">
            <div class="line1"><span class="ident">${esc(ident)}</span>${sub ? `<span class="sub">${esc(sub)}</span>` : ""}${route}</div>
            <div class="line2">${facts}${desc ? ` · ${esc(desc)}` : ""}</div>
          </div>
        </div>`);
    }
    const total = all?.attributes?.total_aircraft;
    const milOn = this._state("military_aircraft")?.state === "on";
    return `
      <ha-card>
        <div class="header" data-entity="${esc(this._ids.all_aircraft || "")}">
          <div class="title">${esc(title)}</div>
          <div class="summary">
            ${total !== undefined ? `<span>${esc(total)} tracked</span>` : ""}
            ${milOn ? `<span class="mil"><ha-icon icon="mdi:shield-airplane"></ha-icon>Military</span>` : ""}
          </div>
        </div>
        ${rows.length ? rows.join("") : `<div class="empty">No aircraft with a known position right now.</div>`}
      </ha-card>`;
  }
}

/* ----- Closest aircraft, in detail ------------------------------------- */

class AdsbClosestAircraftCard extends AdsbBaseCard {
  static watch = ["closest_aircraft"];
  static defaultTitle = "Closest aircraft";
  static style = `
    .hero { display: flex; gap: 14px; align-items: center; padding: 0 16px 8px; }
    .hero ha-icon { --mdc-icon-size: 44px; flex: none; }
    .ident { font-size: 1.6em; font-weight: 600; line-height: 1.2; }
    .sub { color: var(--secondary-text-color); }
    .routebox { margin: 4px 16px 8px; padding: 10px 12px; border-radius: 10px; background: var(--secondary-background-color); display: flex; align-items: center; gap: 10px; }
    .stop { flex: 1; min-width: 0; }
    .stop:last-child { text-align: right; }
    .code { font-size: 1.3em; font-weight: 700; color: var(--primary-color); }
    .city { font-size: 0.85em; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    /* mdi:airplane points north-east; turn it to face the destination */
    .routebox > ha-icon { color: var(--secondary-text-color); transform: rotate(45deg); }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(72px, 1fr)); gap: 8px; padding: 8px 16px 16px; }
    .stat { padding: 8px 10px; border-radius: 10px; background: var(--secondary-background-color); }
    .label { font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.04em; color: var(--secondary-text-color); }
    .stat { min-width: 0; }
    .value { font-size: 1em; font-weight: 600; display: flex; align-items: center; gap: 2px; white-space: nowrap; }
    .value ha-icon { --mdc-icon-size: 16px; flex: none; }
    .emergency { margin: 0 16px 8px; padding: 8px 12px; border-radius: 10px; background: var(--error-color); color: var(--text-primary-color, #fff); font-weight: 600; }
  `;

  getCardSize() {
    return 5;
  }

  renderBody(title) {
    const st = this._state("closest_aircraft");
    const a = st?.attributes || {};
    if (!st || !a.hex) {
      return `<ha-card header="${esc(title)}"><div class="empty">No aircraft with a known position right now.</div></ha-card>`;
    }
    const ident = identOf(a);
    const subParts = [a.tail && a.tail !== "Unknown" && a.tail !== ident ? a.tail : null,
      a.description && a.description !== "Unknown aircraft" ? a.description : null];
    const operator = a.operator ? `<div class="sub">${esc(a.operator)}</div>` : "";
    const alt = Number(a.altitude_ft) || 0;
    const vr = Number(a.vertical_rate_fpm) || 0;
    const trend = vr > 300 ? "mdi:arrow-top-right" : vr < -300 ? "mdi:arrow-bottom-right" : null;
    const heading = typeof a.heading === "number" ? a.heading : null;
    const route = a.route_origin && a.route_destination ? `
      <div class="routebox">
        <div class="stop"><div class="code">${esc(a.route_origin)}</div><div class="city">${esc(a.route_origin_name)}</div></div>
        <ha-icon icon="mdi:airplane"></ha-icon>
        <div class="stop"><div class="code">${esc(a.route_destination)}</div><div class="city">${esc(a.route_destination_name)}</div></div>
      </div>` : "";
    const emergency = a.emergency && a.emergency !== "none"
      ? `<div class="emergency">Emergency: ${esc(a.emergency)}${a.squawk ? ` (squawk ${esc(a.squawk)})` : ""}</div>` : "";
    const stat = (label, value) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`;
    return `
      <ha-card data-entity="${esc(this._ids.closest_aircraft)}">
        <div class="header"><div class="title">${esc(title)}</div></div>
        <div class="hero">
          <ha-icon class="${altBand(a)}" icon="mdi:airplane"></ha-icon>
          <div>
            <div class="ident">${esc(ident)}</div>
            <div class="sub">${esc(subParts.filter(Boolean).join(" · "))}</div>
            ${operator}
          </div>
        </div>
        ${emergency}${route}
        <div class="stats">
          ${stat("Distance", esc(a.distance_display || "?"))}
          ${stat("Altitude", `${a.on_ground ? "Ground" : alt ? `${alt.toLocaleString()} ft` : "?"}${trend ? `<ha-icon icon="${trend}"></ha-icon>` : ""}`)}
          ${stat("Speed", a.speed_kts ? `${Math.round(a.speed_kts)} kts` : "?")}
          ${stat("Heading", heading !== null
            ? `<ha-icon icon="mdi:arrow-up" style="transform: rotate(${heading}deg)"></ha-icon>${compass(heading)}` : "?")}
        </div>
      </ha-card>`;
  }
}

/* ----- Military alert --------------------------------------------------- */

class AdsbMilitaryCard extends AdsbBaseCard {
  static watch = ["military_aircraft", "military_details"];
  static defaultTitle = "Military aircraft";
  static style = `
    .state { display: flex; gap: 14px; align-items: center; padding: 16px; }
    .badge { flex: none; width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
    .badge ha-icon { --mdc-icon-size: 28px; }
    .clear .badge { background: rgba(var(--rgb-success-color, 76, 175, 80), 0.2); color: var(--success-color, #4caf50); }
    .alert .badge { background: rgba(var(--rgb-error-color, 244, 67, 54), 0.2); color: var(--error-color); }
    .headline { font-size: 1.15em; font-weight: 600; }
    .alert .headline { color: var(--error-color); }
    .row { display: flex; gap: 10px; align-items: baseline; padding: 6px 16px; border-top: 1px solid var(--divider-color); }
    .row:last-child { padding-bottom: 12px; }
    .ident { font-weight: 600; }
    .facts { color: var(--secondary-text-color); font-size: 0.85em; }
  `;

  renderBody(title) {
    const present = this._state("military_aircraft")?.state === "on";
    const details = this._state("military_details")?.attributes || {};
    const total = details.total_aircraft;
    if (!present) {
      return `
        <ha-card class="clear" data-entity="${esc(this._ids.military_details || this._ids.military_aircraft)}">
          <div class="state clear">
            <div class="badge"><ha-icon icon="mdi:shield-check"></ha-icon></div>
            <div>
              <div class="headline">${esc(title)}: all clear</div>
              <div class="muted">${total !== undefined ? `None among ${esc(total)} tracked aircraft` : "None detected"}</div>
            </div>
          </div>
        </ha-card>`;
    }
    const rows = [];
    for (let i = 1; details[`military_${i}`]; i++) {
      const m = details[`military_${i}`];
      const alt = Number(m.altitude_ft) || 0;
      const facts = [m.description && m.description !== "Unknown aircraft" ? m.description : null,
        m.distance_display && m.distance_display !== "Unknown" ? m.distance_display : null,
        alt ? `${alt.toLocaleString()} ft` : null].filter(Boolean).map(esc).join(" · ");
      rows.push(`<div class="row"><span class="ident">${esc(identOf(m))}</span><span class="facts">${facts}</span></div>`);
    }
    const count = details.military_count ?? rows.length;
    return `
      <ha-card data-entity="${esc(this._ids.military_details || this._ids.military_aircraft)}">
        <div class="state alert">
          <div class="badge"><ha-icon icon="mdi:shield-airplane"></ha-icon></div>
          <div>
            <div class="headline">${esc(count)} military aircraft detected</div>
            <div class="muted">Matched against the verified military database</div>
          </div>
        </div>
        ${rows.join("")}
      </ha-card>`;
  }
}

/* ----- Stats tile ------------------------------------------------------- */

class AdsbStatsCard extends AdsbBaseCard {
  static watch = ["all_aircraft", "military_details", "military_database_status", "closest_aircraft"];
  static defaultTitle = "ADS-B receiver";
  static style = `
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; padding: 0 16px 16px; }
    .tile { padding: 10px 12px; border-radius: 10px; background: var(--secondary-background-color); min-width: 0; }
    .num { font-size: 1.5em; font-weight: 700; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .label { font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.04em; color: var(--secondary-text-color); }
    .warn { color: var(--error-color); }
    .ok { color: var(--success-color, #4caf50); }
  `;

  renderBody(title) {
    const all = this._state("all_aircraft")?.attributes || {};
    const mil = this._state("military_details")?.attributes || {};
    const db = this._state("military_database_status")?.attributes || {};
    const closest = this._state("closest_aircraft")?.attributes || {};
    const updated = typeof all.last_update === "number"
      ? Math.max(0, Math.round(Date.now() / 1000 - all.last_update)) : null;
    const age = updated === null ? "" : updated < 60 ? `updated ${updated}s ago` : `updated ${Math.round(updated / 60)} min ago`;
    const milCount = mil.military_count ?? 0;
    const tile = (entity, num, label, cls = "") =>
      `<div class="tile" data-entity="${esc(entity || "")}"><div class="num ${cls}">${num}</div><div class="label">${label}</div></div>`;
    return `
      <ha-card>
        <div class="header"><div class="title">${esc(title)}</div><div class="muted">${esc(age)}</div></div>
        <div class="grid">
          ${tile(this._ids.all_aircraft, esc(all.total_aircraft ?? "?"), "Tracked")}
          ${tile(this._ids.closest_aircraft, esc(closest.distance_display || "—"), "Closest")}
          ${tile(this._ids.military_details, esc(milCount), "Military", milCount ? "warn" : "")}
          ${tile(this._ids.military_database_status,
            db.database_loaded ? `<span class="ok">✓</span> ${esc(Number(db.database_size || 0).toLocaleString())}` : `<span class="warn">✗</span>`,
            "Military DB")}
        </div>
      </ha-card>`;
  }
}

/* ----- Registration ----------------------------------------------------- */

const CARDS = [
  ["adsb-aircraft-tracker-card", AdsbAircraftTrackerCard, "ADSB Aircraft Tracker",
    "Nearest aircraft with routes, altitude and speed, plus a military flag."],
  ["adsb-closest-aircraft-card", AdsbClosestAircraftCard, "ADSB Closest Aircraft",
    "The closest aircraft in detail: type, operator, route, altitude trend and heading."],
  ["adsb-military-card", AdsbMilitaryCard, "ADSB Military Alert",
    "All-clear when quiet; lists military aircraft when any are detected."],
  ["adsb-stats-card", AdsbStatsCard, "ADSB Stats",
    "Tracked aircraft, closest distance, military count and database health."],
];

window.customCards = window.customCards || [];
for (const [type, cls, name, description] of CARDS) {
  if (customElements.get(type)) continue;
  customElements.define(type, cls);
  window.customCards.push({
    type, name, description, preview: true,
    documentationURL: "https://github.com/hook-365/adsb-aircraft-tracker",
  });
}
