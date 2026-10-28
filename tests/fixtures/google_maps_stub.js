/* ==========================================================
   01. SIMULASI SDK GOOGLE MAPS UNTUK PENGUJIAN
   Menyediakan peta, marker, dan event tiruan untuk pengujian browser; tidak dipakai sebagai peta aplikasi.
   ========================================================== */

/* Test-only SDK contract double. Never served by the application. */
(() => {
  class Events {
    constructor() { this.listeners = {}; }
    addListener(name, handler) { (this.listeners[name] ||= []).push(handler); return {remove() {}}; }
    emit(name, event) { for (const handler of this.listeners[name] || []) handler(event); }
  }
  class TestMap extends Events {
    constructor(element, options) {
      super(); this.options = options; this.center = options.center;
      this.zoom = options.zoom; this.tilt = options.tilt; this.heading = options.heading;
      window.testGoogleMaps.push(this);
      element.textContent = 'Simulated SDK for automated testing only';
      setTimeout(() => this.emit('tilesloaded'), 20);
    }
    getCenter() { return this.center; }
    setCenter(value) { this.center = value; }
    getZoom() { return this.zoom; }
    setZoom(value) { this.zoom = value; }
    getTilt() { return this.tilt; }
    setTilt(value) { this.tilt = value; this.emit('tilt_changed'); }
    setHeading(value) { this.heading = value; }
    getRenderingType() { return 'VECTOR'; }
    setMapTypeId(value) { this.mapTypeId = value; }
  }
  class TestMarker extends Events {
    constructor(options) { super(); Object.assign(this, options); window.testGoogleMarkers.push(this); }
  }
  window.testGoogleMaps = []; window.testGoogleMarkers = [];
  window.google = {maps: {Map: TestMap, RenderingType: {VECTOR: 'VECTOR'},
    marker: {AdvancedMarkerElement: TestMarker},
    event: {clearInstanceListeners(object) { object.listeners = {}; }, trigger(object, event) { object.emit(event); }}
  }};
  window.kendaragoGoogleMapsReady();
})();
