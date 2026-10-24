// Terravia interactive county map.
//
// Static, client-side choropleth of CDC PLACES (2023) estimates for the
// 14 Massachusetts counties. Reads the same local data files the rest of
// the project ships (data/ma_counties.geojson + data/snapshot_places_ma.csv),
// so it works on GitHub Pages with no API.

(function () {
  "use strict";

  var GEOJSON_URL = "data/ma_counties.geojson";
  var CSV_URL = "data/snapshot_places_ma.csv";

  // Terravia palette (from styles.css) -> light-to-dark green ramp.
  var RAMP = ["#eef4ee", "#cfe0d2", "#a7c6ac", "#6fa17e", "#3d7a5a", "#1d4034"];

  var statusEl = document.getElementById("map-status");
  var selectEl = document.getElementById("measure-select");
  var descEl = document.getElementById("measure-desc");
  var legendEl = document.getElementById("map-legend");

  function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  // --- Minimal CSV parser (handles quoted fields + embedded commas) ---
  function parseCSV(text) {
    var rows = [];
    var row = [];
    var field = "";
    var inQuotes = false;
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      if (inQuotes) {
        if (c === '"') {
          if (text[i + 1] === '"') {
            field += '"';
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          field += c;
        }
      } else if (c === '"') {
        inQuotes = true;
      } else if (c === ",") {
        row.push(field);
        field = "";
      } else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        if (field !== "" || row.length) {
          row.push(field);
          rows.push(row);
          row = [];
          field = "";
        }
      } else {
        field += c;
      }
    }
    if (field !== "" || row.length) {
      row.push(field);
      rows.push(row);
    }
    return rows;
  }

  function rowsToObjects(rows) {
    var header = rows[0];
    var out = [];
    for (var i = 1; i < rows.length; i++) {
      var obj = {};
      for (var j = 0; j < header.length; j++) {
        obj[header[j]] = rows[i][j];
      }
      out.push(obj);
    }
    return out;
  }

  // Build: measures[] (ordered) and byMeasure[measureid][locationid] = {...}
  function indexData(records) {
    var measures = [];
    var measureSeen = {};
    var byMeasure = {};

    records.forEach(function (r) {
      var mid = r.measureid;
      if (!mid) return;
      if (!measureSeen[mid]) {
        measureSeen[mid] = true;
        measures.push({ id: mid, label: r.measure_label });
        byMeasure[mid] = {};
      }
      byMeasure[mid][r.locationid] = {
        name: r.locationname,
        value: parseFloat(r.data_value),
        low: parseFloat(r.low_ci),
        high: parseFloat(r.high_ci),
        population: parseInt(r.total_population, 10),
      };
    });

    return { measures: measures, byMeasure: byMeasure };
  }

  function extent(values) {
    var min = Infinity;
    var max = -Infinity;
    values.forEach(function (v) {
      if (v == null || isNaN(v)) return;
      if (v < min) min = v;
      if (v > max) max = v;
    });
    if (min === Infinity) return [0, 1];
    if (min === max) max = min + 1;
    return [min, max];
  }

  // Equal-interval color buckets across the current measure's range.
  function makeScale(minV, maxV) {
    var buckets = RAMP.length;
    var step = (maxV - minV) / buckets;
    return {
      color: function (v) {
        if (v == null || isNaN(v)) return "#e6e9e2";
        var idx = Math.floor((v - minV) / step);
        if (idx < 0) idx = 0;
        if (idx >= buckets) idx = buckets - 1;
        return RAMP[idx];
      },
      breaks: (function () {
        var b = [];
        for (var i = 0; i <= buckets; i++) b.push(minV + step * i);
        return b;
      })(),
    };
  }

  function fmt(v) {
    return isNaN(v) ? "n/a" : v.toFixed(1) + "%";
  }

  // --- Boot ---
  function init() {
    if (typeof L === "undefined") {
      setStatus("Map library failed to load. Check your connection and refresh.");
      return;
    }

    Promise.all([
      fetch(GEOJSON_URL).then(function (r) {
        if (!r.ok) throw new Error("geojson " + r.status);
        return r.json();
      }),
      fetch(CSV_URL).then(function (r) {
        if (!r.ok) throw new Error("csv " + r.status);
        return r.text();
      }),
    ])
      .then(function (results) {
        build(results[0], rowsToObjects(parseCSV(results[1])));
      })
      .catch(function (err) {
        setStatus("Could not load map data (" + err.message + ").");
      });
  }

  function build(geojson, records) {
    var data = indexData(records);
    if (!data.measures.length) {
      setStatus("No measures found in the data.");
      return;
    }

    var map = L.map("map", {
      scrollWheelZoom: false,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 12,
      minZoom: 6,
    }).addTo(map);

    var currentMeasure = data.measures[0].id;
    var scale = null;

    function styleFor(feature) {
      var rec = data.byMeasure[currentMeasure][feature.properties.locationid];
      return {
        fillColor: scale ? scale.color(rec ? rec.value : NaN) : "#e6e9e2",
        weight: 1,
        opacity: 1,
        color: "#ffffff",
        fillOpacity: 0.85,
      };
    }

    function popupHtml(feature) {
      var rec = data.byMeasure[currentMeasure][feature.properties.locationid];
      var name = feature.properties.name || (rec && rec.name) || "Unknown";
      if (!rec || isNaN(rec.value)) {
        return "<strong>" + name + " County</strong><br>No estimate available.";
      }
      return (
        "<strong>" +
        name +
        " County</strong><br>" +
        "<span class='map-pop-value'>" +
        fmt(rec.value) +
        "</span><br>" +
        "95% CI " +
        fmt(rec.low) +
        " &ndash; " +
        fmt(rec.high) +
        "<br><span class='map-pop-pop'>Pop. " +
        rec.population.toLocaleString() +
        "</span>"
      );
    }

    var geoLayer = L.geoJSON(geojson, {
      style: styleFor,
      onEachFeature: function (feature, layer) {
        layer.bindTooltip(function () {
          return popupHtml(feature);
        }, { sticky: true, direction: "top", className: "map-tooltip" });

        layer.on({
          mouseover: function (e) {
            e.target.setStyle({ weight: 2.5, color: "#20312b", fillOpacity: 0.95 });
            e.target.bringToFront();
          },
          mouseout: function (e) {
            geoLayer.resetStyle(e.target);
          },
          click: function (e) {
            map.fitBounds(e.target.getBounds(), { padding: [20, 20], maxZoom: 10 });
          },
        });
      },
    }).addTo(map);

    map.fitBounds(geoLayer.getBounds(), { padding: [10, 10] });

    function renderLegend() {
      if (!legendEl || !scale) return;
      var rows = "";
      for (var i = 0; i < RAMP.length; i++) {
        var from = scale.breaks[i];
        var to = scale.breaks[i + 1];
        rows +=
          '<div class="map-legend-row">' +
          '<span class="map-legend-swatch" style="background:' + RAMP[i] + '"></span>' +
          "<span>" + from.toFixed(1) + " &ndash; " + to.toFixed(1) + "%</span>" +
          "</div>";
      }
      legendEl.innerHTML = '<p class="map-legend-title">Prevalence</p>' + rows;
    }

    function applyMeasure(mid) {
      currentMeasure = mid;
      var values = Object.keys(data.byMeasure[mid]).map(function (k) {
        return data.byMeasure[mid][k].value;
      });
      var ext = extent(values);
      scale = makeScale(ext[0], ext[1]);
      geoLayer.setStyle(styleFor);
      renderLegend();

      var measure = data.measures.filter(function (m) {
        return m.id === mid;
      })[0];
      if (descEl && measure) descEl.textContent = measure.label;
    }

    // Populate the measure selector.
    data.measures.forEach(function (m, i) {
      var opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = shortLabel(m);
      if (i === 0) opt.selected = true;
      selectEl.appendChild(opt);
    });
    selectEl.addEventListener("change", function () {
      applyMeasure(selectEl.value);
    });

    applyMeasure(currentMeasure);
    setStatus("Showing 14 Massachusetts counties. Click a county to zoom in.");
  }

  // Friendlier names for the dropdown; falls back to the CDC label.
  function shortLabel(m) {
    var map = {
      DIABETES: "Diabetes",
      CASTHMA: "Current asthma",
      BPHIGH: "High blood pressure",
      COPD: "COPD",
      ACCESS2: "Lacks health insurance (18–64)",
      CHECKUP: "Routine checkup",
    };
    return map[m.id] || m.label;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
