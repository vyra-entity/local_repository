import { defineComponent as C, ref as b, computed as I, onMounted as S, openBlock as m, createElementBlock as p, createElementVNode as V, createCommentVNode as E } from "vue";
const T = { class: "vyra-detail-export" }, $ = ["disabled", "title"], U = {
  key: 0,
  class: "vyra-detail-export__spinner"
}, L = {
  key: 1,
  class: "vyra-detail-export__icon"
}, K = ["title"], M = "https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs", B = /* @__PURE__ */ C({
  __name: "ModuleDetailExport",
  props: {
    tab: { default: "info" },
    instanceId: { default: "" },
    moduleName: { default: "module" },
    moduleData: { default: () => ({}) }
  },
  setup(_) {
    const s = _, i = b(!1), c = b(null), y = I(() => ({
      info: "Info",
      functions: "Functions",
      params: "Parameters",
      volatile: "Volatile",
      feeds: "Feeds",
      logs: "Logs"
    })[s.tab] ?? s.tab);
    let f = !1;
    function x() {
      if (f) return;
      f = !0;
      const t = document.createElement("style");
      t.textContent = `
    .vyra-detail-export {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .vyra-detail-export__btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 55px;
      height: 28px;
      padding: 0;
      border: 1px solid var(--p-surface-border, #3d4a5c);
      border-radius: 4px;
      background: transparent;
      color: var(--p-text-color, #ced4da);
      cursor: pointer;
      font-size: 14px;
      transition: background 0.15s, border-color 0.15s;
    }
    .vyra-detail-export__btn:hover:not(:disabled) {
      background: var(--p-surface-hover, #2a3547);
      border-color: var(--p-primary-color, #6c9aff);
      color: var(--p-primary-color, #6c9aff);
    }
    .vyra-detail-export__btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .vyra-detail-export__error {
      color: var(--p-red-400, #f87171);
      font-size: 13px;
    }
  `, document.head.appendChild(t);
    }
    S(x);
    let d = null;
    function v() {
      return d || (d = import(
        /* @vite-ignore */
        M
      ).catch((t) => {
        throw d = null, t;
      })), d;
    }
    function h(t, o) {
      const a = t.info ?? {}, e = [];
      for (const [n, r] of Object.entries(a))
        e.push({ Key: n, Value: r == null ? "" : String(r) });
      return e.length === 0 && o && e.push({ Key: "instance_id", Value: o }), e;
    }
    function g(t) {
      return (t.functions ?? []).map((a) => {
        const e = (n) => (n ?? []).map((r) => `${r.name ?? r.displayname ?? ""}: ${r.datatype ?? ""}`).join(", ");
        return {
          "Function Name": a.functionname ?? a.function_name ?? a.name ?? "",
          "Display Name": a.displayname ?? "",
          Type: a.type ?? "",
          Description: a.description ?? "",
          "Request IN": e(a.params),
          "Response OUT": e(a.returns)
        };
      });
    }
    function w(t) {
      const o = t.params ?? {};
      return Object.entries(o).map(([a, e]) => ({
        Key: a,
        "Display Name": (e == null ? void 0 : e.display_name) ?? (e == null ? void 0 : e.displayname) ?? "",
        Value: (e == null ? void 0 : e.value) == null ? "" : String(e.value),
        Default: (e == null ? void 0 : e.default_value) == null ? "" : String(e.default_value),
        Type: (e == null ? void 0 : e.type) ?? "",
        Description: (e == null ? void 0 : e.description) ?? ""
      }));
    }
    function k(t) {
      const o = t.volatiles ?? {};
      return Object.entries(o).map(([a, e]) => ({
        Key: a,
        Value: e == null ? "" : typeof e == "object" ? JSON.stringify(e) : String(e)
      }));
    }
    function D(t) {
      const o = (a) => (a ?? []).map((e) => ({
        Timestamp: e.ts ?? e.timestamp ?? "",
        State: e.state ?? "",
        Data: e.data == null ? "" : typeof e.data == "object" ? JSON.stringify(e.data) : String(e.data),
        Description: e.description ?? ""
      }));
      return [
        { name: "State Feeds", rows: o(t.stateFeeds) },
        { name: "Error Feeds", rows: o(t.errorFeeds) },
        { name: "News Feeds", rows: o(t.newsFeeds) }
      ];
    }
    function j(t) {
      return (t.logLines ?? []).map((a) => ({
        Timestamp: a.ts ?? "",
        Level: a.level ?? "",
        Logger: a.logger ?? "",
        Message: a.message ?? ""
      }));
    }
    function N(t, o) {
      const a = new Blob([t], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      }), e = URL.createObjectURL(a), n = document.createElement("a");
      n.href = e, n.download = o, document.body.appendChild(n), n.click(), setTimeout(() => {
        document.body.removeChild(n), URL.revokeObjectURL(e);
      }, 100);
    }
    function F(t) {
      const o = t.utils.book_new(), a = (s.moduleName ?? "module").replace(/[^a-z0-9_-]/gi, "_").slice(0, 24), e = (s.instanceId ?? "").slice(0, 4) || "mod", n = `${a}_${e}_${s.tab}_${(/* @__PURE__ */ new Date()).toISOString().slice(0, 10)}.xlsx`;
      if (s.tab === "feeds")
        for (const { name: l, rows: u } of D(s.moduleData)) {
          const O = u.length > 0 ? t.utils.json_to_sheet(u) : t.utils.aoa_to_sheet([["No data"]]);
          t.utils.book_append_sheet(o, O, l);
        }
      else {
        let l;
        switch (s.tab) {
          case "info":
            l = h(s.moduleData, s.instanceId);
            break;
          case "functions":
            l = g(s.moduleData);
            break;
          case "params":
            l = w(s.moduleData);
            break;
          case "volatile":
            l = k(s.moduleData);
            break;
          case "logs":
            l = j(s.moduleData);
            break;
          default:
            l = [];
        }
        const u = l.length > 0 ? t.utils.json_to_sheet(l) : t.utils.aoa_to_sheet([["No data"]]);
        t.utils.book_append_sheet(o, u, s.tab.charAt(0).toUpperCase() + s.tab.slice(1));
      }
      const r = t.write(o, { bookType: "xlsx", type: "array" });
      N(r, n);
    }
    async function R() {
      if (!i.value) {
        i.value = !0, c.value = null;
        try {
          const t = await v();
          F(t);
        } catch (t) {
          console.error("[module-detail-export] download error:", t), c.value = "Export failed";
        } finally {
          i.value = !1;
        }
      }
    }
    return (t, o) => (m(), p("span", T, [
      V("button", {
        class: "vyra-detail-export__btn",
        disabled: i.value,
        title: `Download ${y.value} as xlsx`,
        onClick: R
      }, [
        i.value ? (m(), p("span", U, "⏳")) : (m(), p("span", L, "⬇(.xlsx)"))
      ], 8, $),
      c.value ? (m(), p("span", {
        key: 0,
        class: "vyra-detail-export__error",
        title: c.value
      }, "⚠", 8, K)) : E("", !0)
    ]));
  }
});
export {
  B as default
};
