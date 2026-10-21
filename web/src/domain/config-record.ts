// Agregado do registro de config. Invariantes: sempre 1592 bytes, e só sai pra gravação um registro
// cujo crc_value bate com o q o encode calcularia sobre a base lida do controle.
import { CFG_SIZE } from './packet'
import { decode, encode, recordProblem } from './record'
import type { ConfigDoc } from './types'
import { InvariantError, changeProblem } from './values'

export class ConfigRecord {
  private readonly bytes: Uint8Array

  private constructor(bytes: Uint8Array) {
    this.bytes = bytes
  }

  static fromBytes(bytes: Uint8Array): ConfigRecord {
    if (bytes.length !== CFG_SIZE) throw new InvariantError(`registro tem q ter ${CFG_SIZE} bytes, veio ${bytes.length}`)
    return new ConfigRecord(bytes.slice())
  }

  toBytes(): Uint8Array {
    return this.bytes.slice()
  }

  get crc(): number {
    return new DataView(this.bytes.buffer).getUint32(12, true)
  }

  toDoc(): ConfigDoc {
    return decode(this.bytes)
  }

  withChanges(doc: ConfigDoc): { next: ConfigRecord; changed: string[] } {
    const { record, changed, problems } = encode(doc, this.bytes, changeProblem)
    if (problems.length) throw new InvariantError(problems.join('\n'))
    return { next: new ConfigRecord(record), changed }
  }

  assertWritableOver(base: ConfigRecord): void {
    const problem = recordProblem(this.bytes, base.bytes)
    if (problem) throw new InvariantError(`Gravação barrada: ${problem}`)
  }

  equals(other: ConfigRecord): boolean {
    return this.bytes.every((b, i) => b === other.bytes[i])
  }
}
