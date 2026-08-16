window.USAGI_ANALYTICS_CALLBACK_URL =
  "https://usagi-analytics-lolnt7besa-an.a.run.app/oauth/callback";

const status = document.getElementById("status");
const callbackUrl = window.USAGI_ANALYTICS_CALLBACK_URL;
const source = new URL(window.location.href);
const target = new URL(callbackUrl);

for (const [key, value] of source.searchParams.entries()) {
  target.searchParams.set(key, value);
}

if (!source.searchParams.has("code") && !source.searchParams.has("error")) {
  status.textContent =
    "code または error が見つかりません。TikTokのRedirect URI設定を確認してください。";
} else if (callbackUrl.includes("YOUR_CLOUD_RUN_URL")) {
  status.innerHTML =
    "<code>callback.js</code> の <code>USAGI_ANALYTICS_CALLBACK_URL</code> をCloud Run URLへ変更してください。";
} else {
  window.location.replace(target.toString());
}
