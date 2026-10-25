"use strict";
const byId = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const dialog = byId("camera-dialog");
let state = {cameras: []}, editing = null, removing = null, noticeUntil = 0;
const expanded = new Set(), expandedAudio = new Set(), results = new Map(), testing = new Set(), restarting = new Set(), inspecting = new Set();

async function request(path, method = "GET", payload = null) {
  const response = await fetch(new URL(path, document.baseURI), {
    method, cache: "no-store", credentials: "same-origin",
    headers: method === "GET" ? {} : {"Content-Type": "application/json", "X-CSRF-Token": csrf},
    body: payload === null ? null : JSON.stringify(payload)
  });
  let body;
  try { body = await response.json(); } catch { throw new Error("The camera manager did not answer. Refresh this page."); }
  if (!response.ok) throw new Error(body.error || "The request failed. Try again.");
  return body;
}

function notice(text, kind = "", duration = 0) {
  const element = byId("notice");
  element.textContent = text;
  element.className = `notice ${kind}`;
  noticeUntil = Date.now() + duration;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text, className, handler) {
  const node = element("button", className, text);
  node.type = "button";
  node.addEventListener("click", handler);
  return node;
}

function snippet(title, value, container, rows) {
  const heading = element("div", "snippet-head");
  const area = element("textarea", "snippet");
  area.readOnly = true;
  area.rows = rows;
  area.value = value;
  area.setAttribute("aria-label", `${title} configuration`);
  heading.append(element("span", "", title), button("Copy", "copy", async event => {
    const copyButton = event.currentTarget;
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else { area.select(); if (!document.execCommand("copy")) throw new Error("copy"); }
      copyButton.textContent = "Copied";
    } catch { area.focus(); area.select(); }
  }));
  container.append(heading, area);
}

function render() {
  byId("version").textContent = `v${state.version || "..."}`;
  byId("camera-count").textContent = state.cameras.length;
  byId("ready-count").textContent = state.cameras.filter(camera => camera.status === "ready").length;
  byId("empty").hidden = state.cameras.length !== 0;
  const cards = [];
  for (const camera of state.cameras) {
    const card = element("article", "camera-card");
    const head = element("div", "card-head");
    const symbol = element("div", "camera-symbol");
    symbol.append(document.querySelector(".brand-icon svg").cloneNode(true));
    symbol.setAttribute("aria-hidden", "true");
    const title = element("div", "card-title");
    title.append(element("h2", "card-name", camera.name), element("div", "serial", camera.serial));
    const labels = {ready: "Proxy ready", starting: "Starting", waiting: "Waiting"};
    head.append(symbol, title, element("span", `badge ${camera.status}`, labels[camera.status] || "Waiting"));
    const meta = element("div", "card-meta");
    for (const [label, value] of [["Dashboard stream", camera.stream], ["Local port", String(camera.port)]]) {
      const item = element("div", "meta-item");
      item.append(element("span", "", label), element("code", "", value)); meta.append(item);
    }
    const actions = element("div", "card-actions");
    const test = button(testing.has(camera.port) ? "Checking..." : "Test video", "button secondary test-button", () => testCamera(camera));
    const audioTest = button("Test audio", "button secondary", () => testCamera(camera, true));
    const restart = button(restarting.has(camera.port) ? "Restarting..." : "Restart proxy", "button secondary", () => restartCamera(camera));
    const inspect = button(inspecting.has(camera.port) ? "Analyzing..." : "Analyze cloud", "button secondary", () => inspectCloud(camera));
    const busy = testing.has(camera.port) || restarting.has(camera.port) || inspecting.has(camera.port);
    test.disabled = busy;
    audioTest.disabled = busy;
    restart.disabled = busy;
    inspect.disabled = busy;
    actions.append(test, audioTest, inspect, restart, button("Edit", "button quiet", () => openCamera(camera)), button("Remove", "button quiet", () => openRemove(camera)));
    card.append(head, meta, actions);
    if (results.has(camera.port)) {
      const result = results.get(camera.port);
      card.append(element("div", `test-result ${result.ok ? "good" : "bad"}`, result.message));
    }
    const details = element("details", "connection");
    details.open = expanded.has(camera.port);
    details.addEventListener("toggle", () => details.open ? expanded.add(camera.port) : expanded.delete(camera.port));
    details.append(element("summary", "", "Connection & dashboard setup"));
    details.append(element("p", "", "Merge the stream entry into your existing go2rtc streams section, then add the Lovelace card to your dashboard."));
    details.append(element("p", "", "These default settings request video only. If the 0.2.1 audio settings stopped playback, restore these settings in both go2rtc and Lovelace, then restart go2rtc."));
    snippet("go2rtc", camera.go2rtc, details, 4);
    snippet("Lovelace card", camera.lovelace, details, 8);
    const audioDetails = element("details", "connection");
    audioDetails.open = expandedAudio.has(camera.port);
    audioDetails.addEventListener("toggle", () => audioDetails.open ? expandedAudio.add(camera.port) : expandedAudio.delete(camera.port));
    audioDetails.append(element("summary", "", "Experimental audio test"));
    audioDetails.append(element("p", "", "Close live views and run Test audio first. Try the following only if an audio track is detected. Merge this separate test stream into go2rtc without replacing the working video stream, then restart go2rtc. Use a temporary card and unmute its speaker. Audio playback is not yet verified on BC1 hardware."));
    snippet("go2rtc audio test", camera.go2rtc_audio, audioDetails, 4);
    snippet("Temporary audio card", camera.lovelace_audio, audioDetails, 8);
    details.append(audioDetails);
    card.append(details); cards.push(card);
  }
  byId("cameras").replaceChildren(...cards);
}

async function refresh() {
  try {
    state = await request("api/state"); render();
    if (Date.now() >= noticeUntil) notice(state.message || "Camera manager ready.");
  } catch (error) { notice(error.message, "error", 10000); }
}

function openCamera(camera = null) {
  editing = camera;
  byId("camera-form").reset();
  byId("form-error").hidden = true;
  byId("dialog-title").textContent = camera ? "Edit camera" : "Add new camera";
  byId("save-camera").textContent = camera ? "Save changes" : "Save camera";
  byId("camera-name").value = camera ? camera.name : "";
  const sample = camera ? camera.serial : (state.cameras[0]?.serial || "");
  const separator = sample.lastIndexOf("-");
  byId("hub-serial").value = separator > 0 ? sample.slice(0, separator) : "";
  byId("camera-serial").value = camera ? (separator > 0 ? sample.slice(separator + 1) : sample) : "";
  dialog.showModal();
  byId("camera-name").focus();
}

async function saveCamera(event) {
  event.preventDefault();
  const save = byId("save-camera");
  save.disabled = true; save.textContent = "Saving & verifying...";
  byId("form-error").hidden = true;
  try {
    const result = await request(editing ? `api/cameras/${editing.port}` : "api/cameras", editing ? "PATCH" : "POST", {
      name: byId("camera-name").value, serial: byId("camera-serial").value, hub_serial: byId("hub-serial").value
    });
    dialog.close(); notice(result.message, "success", 12000);
    await refresh();
    window.setTimeout(refresh, 1200);
  } catch (error) {
    byId("form-error").textContent = error.message; byId("form-error").hidden = false;
  } finally { save.disabled = false; save.textContent = editing ? "Save changes" : "Save camera"; }
}

function openRemove(camera) {
  removing = camera;
  byId("remove-error").hidden = true;
  byId("remove-description").textContent = `Remove ${camera.name} from your camera manager?`;
  byId("remove-dialog").showModal();
}

async function removeCamera(event) {
  event.preventDefault();
  const confirm = byId("confirm-remove"); confirm.disabled = true;
  try {
    const result = await request(`api/cameras/${removing.port}`, "DELETE", {});
    byId("remove-dialog").close(); notice(result.message, "success", 12000);
    results.delete(removing.port); expanded.delete(removing.port); expandedAudio.delete(removing.port);
    await refresh(); window.setTimeout(refresh, 1200);
  } catch (error) { byId("remove-error").textContent = error.message; byId("remove-error").hidden = false; }
  finally { confirm.disabled = false; }
}

async function inspectCloud(camera) {
  inspecting.add(camera.port); render();
  try { results.set(camera.port, await request(`api/cameras/${camera.port}/inspect-cloud`, "POST", {})); }
  catch (error) { results.set(camera.port, {ok: false, message: error.message}); }
  finally { inspecting.delete(camera.port); render(); }
}

async function restartCamera(camera) {
  restarting.add(camera.port); render();
  try { results.set(camera.port, await request(`api/cameras/${camera.port}/restart`, "POST", {})); }
  catch (error) { results.set(camera.port, {ok: false, message: error.message}); }
  finally { restarting.delete(camera.port); render(); }
}

async function testCamera(camera, audio = false) {
  testing.add(camera.port); render();
  try { results.set(camera.port, await request(`api/cameras/${camera.port}/${audio ? "test-audio" : "test"}`, "POST", {})); }
  catch (error) { results.set(camera.port, {ok: false, message: error.message}); }
  finally { testing.delete(camera.port); render(); }
}

byId("add-camera").addEventListener("click", () => openCamera());
byId("add-first-camera").addEventListener("click", () => openCamera());
byId("camera-form").addEventListener("submit", saveCamera);
for (const id of ["close-dialog", "cancel-dialog"]) byId(id).addEventListener("click", () => dialog.close());
for (const id of ["close-remove", "cancel-remove"]) byId(id).addEventListener("click", () => byId("remove-dialog").close());
byId("remove-form").addEventListener("submit", removeCamera);
refresh();
window.setInterval(() => { if (!document.hidden) refresh(); }, 5000);
