;; Counter Widget — VYRA Plugin Logic
;; WebAssembly Text Format (WAT) Source
;;
;; Exportierte Funktionen:
;;   init(initial_count: i32, step: i32) -> i32
;;   increment(step_override: i32) -> i32   (0 = nutze gespeicherten step)
;;   reset() -> i32
;;   get_count() -> i32
;;   get_step() -> i32
;;
;; Die Logik hält den Zähler-State vollständig im WASM-Speicher (globals).
;; Kommunikation mit Python über Integer Rückgabewerte.
;; In Phase 2 (Extism) werden die Parameter/Rückgaben über Host-Memory abgewickelt.

(module
  ;; Zähler-State als mutable globals
  (global $count (mut i32) (i32.const 0))
  (global $step  (mut i32) (i32.const 1))

  ;; init(initial_count: i32, step_val: i32) -> i32
  ;; Initialisiert den Zähler und speichert die Schrittweite.
  ;; Gibt den Startwert zurück.
  (func $init (export "init") (param $initial i32) (param $step_val i32) (result i32)
    local.get $initial
    global.set $count
    local.get $step_val
    global.set $step
    global.get $count
  )

  ;; increment(step_override: i32) -> i32
  ;; Erhöht den Zähler.
  ;;   step_override > 0 -> nutze diesen Wert
  ;;   step_override == 0 -> nutze gespeicherten $step
  ;; Gibt den neuen Zählerstand zurück.
  (func $increment (export "increment") (param $step_ov i32) (result i32)
    local.get $step_ov
    i32.const 0
    i32.gt_s
    (if (result i32)
      (then
        global.get $count
        local.get $step_ov
        i32.add
      )
      (else
        global.get $count
        global.get $step
        i32.add
      )
    )
    global.set $count
    global.get $count
  )

  ;; reset() -> i32
  ;; Setzt den Zähler auf 0 zurück. Gibt 0 zurück.
  (func $reset (export "reset") (result i32)
    i32.const 0
    global.set $count
    i32.const 0
  )

  ;; get_count() -> i32
  ;; Gibt den aktuellen Zählerstand zurück.
  (func $get_count (export "get_count") (result i32)
    global.get $count
  )

  ;; get_step() -> i32
  ;; Gibt die gespeicherte Schrittweite zurück.
  (func $get_step (export "get_step") (result i32)
    global.get $step
  )
)
