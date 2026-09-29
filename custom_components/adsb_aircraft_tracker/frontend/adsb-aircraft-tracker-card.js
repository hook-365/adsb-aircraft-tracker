/*
 * ADSB Aircraft Tracker card.
 *
 * Served and auto-loaded by the integration (see __init__.py), so it shows up
 * in the dashboard "Add card" picker with no manual resource setup.
 *
 * The card never hardcodes entity ids. It finds the tracker's entities through
 * the entity registry by platform + device + translation_key, so it works on
 * old installs (whatever ids they registered), new installs, renamed entities
 * and multiple feeders alike.
 */

const DOMAIN = "adsb_aircraft_tracker";
const CARD_TYPE = "adsb-aircraft-tracker-card";

// translation_key -> role, plus an entity_id suffix fallback for registries
// that haven't picked up translation keys yet (pre-1.6.1 entities get them on
// their first load with 1.6.1, so this only matters very briefly).
const ROLES = {
  closest_aircraft: /_closest_aircraft$/,
  top_aircraft: /_nearest_\d+_aircraft$/,
  all_aircraft: /_all_aircraft$/,
  military_aircraft: /_military_aircraft_present$/,
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);

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

class AdsbAircraftTrackerCard extends HTMLElement {
  setConfig(config) {
    this._config = { count: 5, ...config };
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
      this._entities = trackerEntities(hass, this._config.device_id);
      this._lastKey = undefined;
    }
    // Re-render only when one of our entities actually changed
    const key = Object.values(this._entities).map((id) => hass.states[id]?.last_updated).join("|");
    if (key === this._lastKey) return;
    this._lastKey = key;
    this._render();
  }

  getCardSize() {
    return 2 + Math.min(this._config?.count ?? 5, 5);
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId }, bubbles: true, composed: true,
    }));
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const hass = this._hass;
    const ids = this._entities || trackerEntities(hass, this._config.device_id);
    const title = this._config.title ?? "Aircraft";

    if (!ids.top_aircraft && !ids.all_aircraft) {
      this.shadowRoot.innerHTML = `
        <ha-card header="${esc(title)}">
          <div class="empty">No ADSB Aircraft Tracker entities found${this._config.device_id ? " for the selected tracker" : ""}.</div>
        </ha-card>${STYLE}`;
      return;
    }

    const all = hass.states[ids.all_aircraft];
    const top = hass.states[ids.top_aircraft];
    const military = hass.states[ids.military_aircraft];
    const total = all?.attributes?.total_aircraft;
    const count = Math.max(1, Math.min(Number(this._config.count) || 5, 5));

    const rows = [];
    for (let i = 1; i <= count; i++) {
      const a = top?.attributes?.[`aircraft_${i}`];
      if (!a) break;
      const ident = a.flight || (a.tail && a.tail !== "Unknown" ? a.tail : a.hex) || "Unknown";
      const sub = a.tail && a.tail !== "Unknown" && a.tail !== ident ? a.tail : "";
      const alt = Number(a.altitude_ft) || 0;
      const band = alt === 0 ? "ground" : alt < 3000 ? "low" : alt < 10000 ? "mid" : "high";
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
        <div class="row" data-entity="${esc(ids.top_aircraft)}">
          <ha-icon class="${band}" icon="mdi:airplane"></ha-icon>
          <div class="main">
            <div class="line1"><span class="ident">${esc(ident)}</span>${sub ? `<span class="sub">${esc(sub)}</span>` : ""}${route}</div>
            <div class="line2">${facts}${desc ? ` · ${esc(desc)}` : ""}</div>
          </div>
        </div>`);
    }

    const milOn = military?.state === "on";
    this.shadowRoot.innerHTML = `
      <ha-card>
        <div class="header" data-entity="${esc(ids.all_aircraft || "")}">
          <div class="title">${esc(title)}</div>
          <div class="summary">
            ${total !== undefined ? `<span>${esc(total)} tracked</span>` : ""}
            ${milOn ? `<span class="mil" data-entity="${esc(ids.military_aircraft)}"><ha-icon icon="mdi:shield-airplane"></ha-icon>Military</span>` : ""}
          </div>
        </div>
        ${rows.length ? rows.join("") : `<div class="empty">No aircraft with a known position right now.</div>`}
      </ha-card>${STYLE}`;

    this.shadowRoot.querySelectorAll("[data-entity]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._moreInfo(el.dataset.entity);
      });
    });
  }

  // Visual editor: pick which tracker (device), how many aircraft, title.
  static getConfigForm() {
    return {
      schema: [
        { name: "device_id", selector: { device: { integration: DOMAIN } } },
        { name: "count", default: 5, selector: { number: { min: 1, max: 5, mode: "slider" } } },
        { name: "title", selector: { text: {} } },
      ],
      computeLabel: (s) => ({
        device_id: "Tracker",
        count: "Aircraft to show",
        title: "Title",
      })[s.name],
      computeHelper: (s) => (s.name === "device_id"
        ? "Leave empty to use the first ADSB tracker found." : undefined),
    };
  }

  static getStubConfig(hass) {
    return { device_id: firstTrackerDevice(hass), count: 5 };
  }
}

const STYLE = `<style>
  ha-card { overflow: hidden; }
  .header { display: flex; justify-content: space-between; align-items: baseline;
    padding: 16px 16px 8px; cursor: pointer; gap: 8px; }
  .title { font-size: 1.25em; font-weight: 500; }
  .summary { display: flex; gap: 10px; align-items: center; color: var(--secondary-text-color); font-size: 0.9em; }
  .mil { display: inline-flex; align-items: center; gap: 4px; color: var(--error-color); font-weight: 600; cursor: pointer; }
  .mil ha-icon { --mdc-icon-size: 18px; }
  .row { display: flex; gap: 12px; align-items: center; padding: 8px 16px; cursor: pointer; }
  .row:hover { background: var(--secondary-background-color); }
  .row:last-child { padding-bottom: 14px; }
  .row ha-icon { flex: none; --mdc-icon-size: 22px; }
  .row ha-icon.high { color: var(--blue-color, #2196f3); }
  .row ha-icon.mid { color: var(--orange-color, #ff9800); }
  .row ha-icon.low { color: var(--deep-orange-color, #ff5722); }
  .row ha-icon.ground { color: var(--disabled-text-color); }
  .main { min-width: 0; flex: 1; }
  .line1 { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  .ident { font-weight: 600; }
  .sub { color: var(--secondary-text-color); font-size: 0.85em; }
  .route { margin-left: auto; font-size: 0.85em; font-weight: 600; color: var(--primary-color); white-space: nowrap; }
  .line2 { color: var(--secondary-text-color); font-size: 0.85em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .empty { padding: 16px; color: var(--secondary-text-color); }
</style>`;

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, AdsbAircraftTrackerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: "ADSB Aircraft Tracker",
    description: "Nearest aircraft with routes, altitude and speed, plus a military alert.",
    preview: true,
    documentationURL: "https://github.com/hook-365/adsb-aircraft-tracker",
  });
}
