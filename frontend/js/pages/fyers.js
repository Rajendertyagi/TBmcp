// FYERS credentials / login page. Saves FYERS App ID + secret (+ PIN/TOTP) to the
// app folder and drives the FYERS login flow. Two paths, like the Upstox page but
// tailored to FYERS:
//   - "Get Login Link" opens the FYERS OAuth URL; FYERS bounces the browser back
//     to /fyers/callback and the token is exchanged automatically (one-click).
//   - "Login with TOTP" performs the daily auto-login server-side (no browser),
//     the dependable path now that FYERS refresh tokens are unreliable.
// After a successful login it asks the router to refresh the current page.

import { api } from "../api.js";
import { el, setStatusById } from "../utils/dom.js";
import { refreshCurrent } from "../router.js";

// The redirect URI registered with FYERS. The WebUI already runs on this exact
// host:port, and the server catches the code at /fyers/callback for one-click login.
var DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/fyers/callback";

export function createFyersPage() {
  function mount(container) {
    container.innerHTML =
      '<div class="tbmcp-setup">' +
      '<div class="tbmcp-setup-title">FYERS API Setup</div>' +
      '<div class="flex items-center gap-4" style="flex-wrap:wrap;">' +
      '<input id="fyAppId" placeholder="App ID (e.g. XXXX-XXXX)" class="tbmcp-input" style="max-width:280px;">' +
      '<input id="fySecret" type="password" placeholder="App Secret" class="tbmcp-input" style="max-width:280px;">' +
      '<input id="fyPin" type="password" placeholder="Trading PIN" class="tbmcp-input" style="max-width:160px;">' +
      '<input id="fyTotp" type="password" placeholder="TOTP Secret" class="tbmcp-input" style="max-width:280px;">' +
      '<input id="fyRedirect" placeholder="Redirect URI" class="tbmcp-input" style="max-width:380px;">' +
      '<button id="fySave">Save</button>' +
      "</div>" +
      '<div class="tbmcp-status" id="fySetupStatus"></div>' +
      "</div>" +
      '<div class="tbmcp-divider"></div>' +
      '<div class="tbmcp-setup">' +
      '<div class="tbmcp-setup-title">Connect / Re-login to FYERS</div>' +
      '<div class="flex items-center gap-4" style="flex-wrap:wrap;">' +
      '<button id="fyGetLogin">Get Login Link</button>' +
      '<button id="fyTotpLogin">Login with TOTP</button>' +
      '<span id="fyLoginLink"></span>' +
      "</div>" +
      '<div class="tbmcp-status" id="fyLoginStatus"></div>' +
      '<div class="flex items-center gap-4" style="margin-top:10px;flex-wrap:wrap;">' +
      '<input id="fyCode" placeholder="Paste the \'auth_code\' from redirect URL" class="tbmcp-input" style="max-width:380px;">' +
      '<button id="fyCompleteLogin">Complete Login</button>' +
      "</div>" +
      "</div>";

    // Prefill from server.
    api.fyersSettings().then(function (res) {
      if (res.ok && res.body) {
        if (res.body.app_id) el("fyAppId").value = res.body.app_id;
        el("fyRedirect").value = res.body.redirect_uri || DEFAULT_REDIRECT_URI;
      } else {
        el("fyRedirect").value = DEFAULT_REDIRECT_URI;
      }
    });
    // Show whether we are already connected.
    api.fyersLoginStatus().then(function (res) {
      if (res.ok && res.body && res.body.connected) {
        setStatusById("fyLoginStatus", "Already connected to FYERS. You can re-login any time.", "ok");
      }
    });

    el("fySave").addEventListener("click", function () {
      var appId = el("fyAppId").value.trim();
      var secret = el("fySecret").value.trim();
      var pin = el("fyPin").value.trim();
      var totp = el("fyTotp").value.trim();
      var redirect = el("fyRedirect").value.trim() || DEFAULT_REDIRECT_URI;
      if (!appId || !secret) {
        setStatusById("fySetupStatus", "Please enter both the App ID and the App Secret.", "err");
        return;
      }
      api.saveFyersSettings({
        app_id: appId, secret: secret, pin: pin, totp_secret: totp, redirect_uri: redirect,
      }).then(function (res) {
        if (res.ok) setStatusById("fySetupStatus", "Saved to the app folder. FYERS is now enabled — connect below.", "ok");
        else setStatusById("fySetupStatus", "Save failed: " + (res.body.error || res.status), "err");
      });
    });

    el("fyGetLogin").addEventListener("click", function () {
      var appId = el("fyAppId").value.trim();
      var redirect = el("fyRedirect").value.trim() || DEFAULT_REDIRECT_URI;
      if (!appId) {
        setStatusById("fyLoginStatus", "Enter your App ID (and Save) before connecting.", "err");
        return;
      }
      api.fyersLoginUrl(appId, redirect).then(function (res) {
        if (!res.ok || res.body.error) {
          setStatusById("fyLoginStatus", res.body.error || "Could not build login URL.", "err");
          return;
        }
        el("fyLoginLink").innerHTML =
          '<a href="' + res.body.url + '" target="_blank" rel="noopener" ' +
          'style="color:#58a6ff;font-weight:600;text-decoration:underline;">Open FYERS login in a new tab &rarr;</a>';
        setStatusById(
          "fyLoginStatus",
          "Log in at FYERS. You'll be sent back and connected automatically — " +
          "no need to copy any code.",
          "ok"
        );
      });
    });

    el("fyTotpLogin").addEventListener("click", function () {
      setStatusById("fyLoginStatus", "Attempting daily TOTP login…", "ok");
      api.fyersTotpLogin().then(function (res) {
        if (res.ok) {
          setStatusById("fyLoginStatus", "Connected via TOTP! Token saved (auto-renew on). Loading data…", "ok");
          refreshCurrent();
        } else {
          setStatusById("fyLoginStatus", "TOTP login failed: " + (res.body.error || res.status) +
            "  (Need FYERS_TOTP_SECRET + PIN in your saved settings.)", "err");
        }
      });
    });

    el("fyCompleteLogin").addEventListener("click", function () {
      var code = el("fyCode").value.trim();
      var redirect = el("fyRedirect").value.trim();
      if (!code) {
        setStatusById("fyLoginStatus", "Paste the 'auth_code' from the redirect URL first.", "err");
        return;
      }
      api.fyersLogin(code, redirect).then(function (res) {
        if (res.ok) {
          setStatusById("fyLoginStatus", "Connected! Token saved (auto-renew on). Loading data…", "ok");
          refreshCurrent();
        } else {
          setStatusById("fyLoginStatus", "Login failed: " + (res.body.error || res.status), "err");
        }
      });
    });
  }

  return { mount: mount };
}

