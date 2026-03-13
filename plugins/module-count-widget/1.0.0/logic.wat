;; Module Count Widget — VYRA Plugin Logic
;; WebAssembly Text Format (WAT) Source
;;
;; This is a stateful cache shim for the module-count widget.
;; The actual module count data is fetched by the frontend directly
;; from the v2_modulemanager REST API. The WASM module provides a
;; minimal counter state so the PluginRuntime has a callable backend.
;;
;; Exported functions:
;;   init(initial_count: i32) -> i32   — called by PluginRuntime on load
;;   set_count(count: i32)    -> i32   — update cached module count
;;   get_count()              -> i32   — retrieve cached module count
;;   set_instances(n: i32)    -> i32   — update cached total instances
;;   get_instances()          -> i32   — retrieve cached total instances

(module
  ;; Cached state — updated by the plugin bridge via set_count/set_instances
  (global $module_count     (mut i32) (i32.const 0))
  (global $total_instances  (mut i32) (i32.const 0))

  ;; init(initial_count: i32) -> i32
  ;; Initialise cached count; called once by PluginRuntime.
  ;; Returns initial_count so the caller can verify round-trip.
  (func $init (export "init") (param $initial i32) (result i32)
    local.get $initial
    global.set $module_count
    global.get $module_count
  )

  ;; set_count(count: i32) -> i32
  ;; Store a new module count; returns the stored value.
  (func $set_count (export "set_count") (param $n i32) (result i32)
    local.get $n
    global.set $module_count
    global.get $module_count
  )

  ;; get_count() -> i32
  ;; Return the cached module count.
  (func $get_count (export "get_count") (result i32)
    global.get $module_count
  )

  ;; set_instances(n: i32) -> i32
  ;; Store the total instance count; returns the stored value.
  (func $set_instances (export "set_instances") (param $n i32) (result i32)
    local.get $n
    global.set $total_instances
    global.get $total_instances
  )

  ;; get_instances() -> i32
  ;; Return the cached total instance count.
  (func $get_instances (export "get_instances") (result i32)
    global.get $total_instances
  )
)
