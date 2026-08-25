import test from "node:test";
import assert from "node:assert/strict";

globalThis.window = {
  Capacitor: { isNativePlatform: () => true },
  location: { protocol: "http:" },
  dispatchEvent() {},
};
globalThis.localStorage = {
  getItem(key) { return key === "growmaster:server-url" ? "http://localhost:3000" : null; },
  setItem() {},
  removeItem() {},
};

const { apiFetch, apiRequest } = await import("./platform.js");

test("JSON request bodies automatically include the content type", async () => {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  };

  await apiFetch("/api/license/activate", {
    method: "POST",
    body: JSON.stringify({ token: "signed-license" }),
  });

  assert.equal(request.options.headers.get("Content-Type"), "application/json");
});

test("validation responses show the server message", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    detail: [{ msg: "Input should be a valid dictionary." }],
  }), { status: 422, headers: { "Content-Type": "application/json" } });

  await assert.rejects(
    apiRequest("/api/license/activate", { method: "POST", body: "{}" }),
    /Input should be a valid dictionary/,
  );
});
