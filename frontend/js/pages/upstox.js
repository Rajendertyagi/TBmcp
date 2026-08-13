// Upstox credentials / login page. Saves API key+secret to the app folder and
// drives the OAuth login flow. After a successful login it asks the router to
// refresh whatever page is currently visible.

import { api } from "../api.js";
import { el, setStatusById } from "../utils/dom.js";
import { refreshCurrent } from "../router.js";

// The redirect URI registered with Upstox. The WebUI already runs on this exact
// host:port, and the server catches the code at /upstox/callback for one-click login.
var DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/upstox/callback";

export function createUpstoxPage() {
  function mount(container) {
    container.innerHTML =
      '<div class="tbmcp-setup">' +
      '<div class="tbmcp-setup-title">Upstox API Setup</div>' +
      '<div class="flex items-center gap-4" style="flex-wrap:wrap;">' +
      '<input id="apikey" placeholder="API Key" class="tbmcp-input" style="max-width:280px;">' +
      '<input id="apisecret" type="password" placeholder="API Secret" class="tbmcp-input" style="max-width:280px;">' +
      '<input id="redirect" placeholder="Redirect URI" class="tbmcp-input" style="max-width:380px;">' +
      '<button id="saveCreds">Save</button>' +
      "</div>" +
      '<div class="tbmcp-status" id="setupStatus"></div>' +
      "</div>" +
      '<div class="tbmcp-divider"></div>' +
      '<div class="tbmcp-setup">' +
      '<div class="tbmcp-setup-title">Connect / Re-login to Upstox</div>' +
      '<div class="flex items-center gap-4" style="flex-wrap:wrap;">' +
      '<button id="getLogin">Get Login Link</button>' +
      '<span id="loginLink"></span>' +
      "</div>" +
      '<div class="tbmcp-status" id="loginStatus"></div>' +
      '<div class="flex items-center gap-4" style="margin-top:10px;flex-wrap:wrap;">' +
      '<input id="code" placeholder="Paste the \'code\' from redirect URL" class="tbmcp-input" style="max-width:380px;">' +
      '<button id="completeLogin">Complete Login</button>' +
      "</div>" +
      "</div>";

    // Prefill from server.
    api.getSettings().then(function (res) {
      if (res.ok && res.body) {
        if (res.body.api_key) el("apikey").value = res.body.api_key;
        el("redirect").value = res.body.redirect_uri || DEFAULT_REDIRECT_URI;
      } else {
        el("redirect").value = DEFAULT_REDIRECT_URI;
      }
    });
    // Show whether we are already connected.
    api.loginStatus().then(function (res) {
      if (res.ok && res.body && res.body.connected) {
        setStatusById("loginStatus", "Already connected to Upstox. You can re-login any time.", "ok");
      }
    });

    el("saveCreds").addEventListener("click", function () {
      var key = el("apikey").value.trim();
      var secret = el("apisecret").value.trim();
      var redirect = el("redirect").value.trim();
      if (!key || !secret) {
        setStatusById("setupStatus", "Please enter both the API Key and the API Secret.", "err");
        return;
      }
      api.saveSettings({ api_key: key, api_secret: secret, redirect_uri: redirect }).then(function (res) {
        if (res.ok) setStatusById("setupStatus", "Saved to the app folder. Then connect below (or click Load).", "ok");
        else setStatusById("setupStatus", "Save failed: " + (res.body.error || res.status), "err");
      });
    });

    el("getLogin").addEventListener("click", function () {
      var key = el("apikey").value.trim();
      var redirect = el("redirect").value.trim() || DEFAULT_REDIRECT_URI;
      if (!key) {
        setStatusById("loginStatus", "Enter your API Key (and Save) before connecting.", "err");
        return;
      }
      api.loginUrl(key, redirect).then(function (res) {
        if (!res.ok || res.body.error) {
          setStatusById("loginStatus", res.body.error || "Could not build login URL.", "err");
          return;
        }
        el("loginLink").innerHTML =
          '<a href="' + res.body.url + '" target="_blank" rel="noopener" ' +
          'style="color:#58a6ff;font-weight:600;text-decoration:underline;">Open Upstox login in a new tab &rarr;</a>';
        setStatusById(
          "loginStatus",
          "Log in at Upstox. You'll be sent back and connected automatically — " +
          "no need to copy any code.",
          "ok"
        );
      });
    });

    el("completeLogin").addEventListener("click", function () {
      var code = el("code").value.trim();
      var redirect = el("redirect").value.trim();
      if (!code) {
        setStatusById("loginStatus", "Paste the 'code' from the redirect URL first.", "err");
        return;
      }
      api.login(code, redirect).then(function (res) {
        if (res.ok) {
          setStatusById("loginStatus", "Connected! Token saved (auto-renew on). Loading data…", "ok");
          refreshCurrent();
        } else {
          setStatusById("loginStatus", "Login failed: " + (res.body.error || res.status), "err");
        }
      });
    });
  }

  return { mount: mount };
}
