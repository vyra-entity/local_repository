import { defineComponent as b, ref as u, computed as I, onMounted as k, onUnmounted as M, openBlock as a, createElementBlock as o, createElementVNode as t, toDisplayString as s, normalizeClass as h, createCommentVNode as c, Fragment as E, renderList as T } from "vue";
const C = { class: "vyra-module-count-widget" }, L = { class: "vyra-module-count-widget__header" }, N = { class: "vyra-module-count-widget__title" }, O = {
  key: 0,
  class: "vyra-module-count-widget__secondary"
}, j = { class: "vyra-module-count-widget__secondary-value" }, B = {
  key: 1,
  class: "vyra-module-count-widget__list"
}, D = {
  key: 2,
  class: "vyra-module-count-widget__error"
}, F = { class: "vyra-module-count-widget__footer" }, P = {
  key: 0,
  class: "vyra-module-count-widget__ts"
}, S = ["disabled"], U = "/v2_modulemanager/api/modules/instances", x = /* @__PURE__ */ b({
  __name: "ModuleCountWidget",
  props: {
    label: { default: "Installed Modules" },
    refreshIntervalMs: { default: 5e3 },
    showInstances: { type: Boolean, default: !0 }
  },
  setup(v) {
    const p = v, i = u(null), _ = u(null), m = u([]), d = u(!1), l = u(null), g = u(null);
    let r = null;
    const w = I(() => g.value ? g.value.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : null), y = async () => {
      if (!d.value) {
        d.value = !0, l.value = null;
        try {
          const n = await fetch(U, { credentials: "same-origin" });
          if (!n.ok) throw new Error(`HTTP ${n.status}`);
          const e = await n.json();
          i.value = e.total_modules ?? Object.keys(e.modules ?? {}).length, _.value = e.total_instances ?? 0, m.value = Object.keys(e.modules ?? {}), g.value = /* @__PURE__ */ new Date();
        } catch (n) {
          l.value = `API unavailable (${n.message})`;
        } finally {
          d.value = !1;
        }
      }
    };
    return k(() => {
      y(), r = setInterval(y, p.refreshIntervalMs);
    }), M(() => {
      r !== null && (clearInterval(r), r = null);
    }), (n, e) => (a(), o("div", C, [
      t("div", L, [
        t("span", N, s(v.label), 1),
        t("span", {
          class: h(["vyra-module-count-widget__badge", l.value ? "vyra-module-count-widget__badge--offline" : "vyra-module-count-widget__badge--live"])
        }, s(l.value ? "OFFLINE" : "LIVE"), 3)
      ]),
      t("div", {
        class: h(["vyra-module-count-widget__value", { "vyra-module-count-widget__value--loading": d.value && i.value === null }]),
        title: "Total distinct module types installed"
      }, s(i.value !== null ? i.value : "–"), 3),
      e[1] || (e[1] = t("div", { class: "vyra-module-count-widget__unit" }, "modules", -1)),
      v.showInstances && !l.value ? (a(), o("div", O, [
        e[0] || (e[0] = t("span", { class: "vyra-module-count-widget__secondary-label" }, "instances", -1)),
        t("span", j, s(_.value !== null ? _.value : "–"), 1)
      ])) : c("", !0),
      m.value.length > 0 && !l.value ? (a(), o("ul", B, [
        (a(!0), o(E, null, T(m.value, (f) => (a(), o("li", {
          key: f,
          class: "vyra-module-count-widget__list-item"
        }, s(f), 1))), 128))
      ])) : c("", !0),
      l.value ? (a(), o("div", D, s(l.value), 1)) : c("", !0),
      t("div", F, [
        w.value ? (a(), o("span", P, "updated " + s(w.value), 1)) : c("", !0),
        t("button", {
          class: "vyra-module-count-widget__refresh-btn",
          disabled: d.value,
          onClick: y,
          title: "Refresh now"
        }, "↻", 8, S)
      ])
    ]));
  }
});
export {
  x as default
};
