// Formato do documento q o config.decode devolve: mesmo JSON do `u2ctl dump`, por isso snake_case.
// Valor desconhecido vem em hex ("0xffffffff" = flash apagada), igual ao Python.

export interface Range {
  flag: string
  left_start: number
  left_end: number
  right_start: number
  right_end: number
}

export interface MacroRecord {
  name: string
  gamepad_mode: number
  special_flag: number
  max_steps: number
  offset: number
  key_map: string
  cycles_num: number
  interval_ms: number
}

export interface Slot {
  flag: string
  name: string
  rumble: { flag: string; left: number | null; right: number | null }
  sticks: Range
  triggers: Range
  xinput_rumble: Range
  special: { flag: string; features: string[] | string }
  mapping: { flag: string; [button: string]: string }
  macros: { flag: string; total_cnt: number; records: MacroRecord[] }
  sixaxis: { flag: string; keys_map: string; trigger_mode: number; sensitivity: number; dead_compensate: number; mapping_type: number }
  led_dynamic: { flag: string; color: string; bg_color: string }
  led_hotwheel: { flag: string; color: string; bg_color: string; speed: number }
  led_single: { flag: string; colors: string[] }
}

export interface ConfigDoc {
  crc_value: number
  gamepad_mode: number
  cur_slot: number
  slots: [Slot, Slot, Slot]
}
