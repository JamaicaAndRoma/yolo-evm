#!/usr/bin/env python3

import argparse
import os

from smol_evm.context import ExecutionContext
from smol_evm.opcodes import decode_opcode, JUMP, STOP, REVERT, RETURN, INVALID, JUMPDEST

from dataclasses import dataclass
from typing import Sequence, List

TERMINATING = set((JUMP.opcode, STOP.opcode, REVERT.opcode, RETURN.opcode, INVALID.opcode))


def strip_0x(s: str):
    return s[2:] if s and s.startswith("0x") else s


@dataclass
class DataSection:
    start_pc: int
    data: bytes = b""

    def render(self, output: List[str]):
        data_format_str = f"{{:04x}}: DATA 0x{{:0{len(self.data) * 2}x}}"
        output.append(data_format_str.format(self.start_pc, int.from_bytes(self.data, byteorder="big")))


def disassemble(code: bytes) -> Sequence[str]:
    output = []
    reading_code = True
    data_section = None

    context = ExecutionContext(code=code)

    while context.pc < len(code):
        original_pc = context.pc
        pc_str = f"{original_pc:04x}"

        # increments pc by instruction length
        insn = decode_opcode(context)
        push_data = code[original_pc + 1 : original_pc + 1 + insn.push_width()] if insn.is_push() else b""

        # switch back to code mode if we encounter a JUMPDEST
        reading_code = reading_code or insn.opcode is JUMPDEST.opcode

        if reading_code:
            if data_section is not None:
                data_section.render(output)
                data_section = None

            if insn.is_push() and len(push_data) < insn.push_width():
                # make sure we handle truncated PUSH arguments
                output.append(f"{pc_str}: PUSH{insn.push_width()} 0x{push_data.hex()} # truncated")
            else:
                output.append(f"{pc_str}: {insn}")

            reading_code = insn.opcode not in TERMINATING

        else:
            # just like the algorithm for valid jump destination validation,
            # we parse PUSH instructions and skip their arguments (so no JUMPDESTs can hide there)
            if data_section is None:
                data_section = DataSection(original_pc)

            data_section.data += insn.opcode.to_bytes(1, byteorder="big")
            data_section.data += push_data

    if data_section is not None:
        data_section.render(output)

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="hex data of the code to run", required=True)
    args = parser.parse_args()

    # is it a file? if so, load the contents
    if os.path.exists(args.code):
        with open(args.code, "r") as f:
            code = bytes.fromhex(strip_0x(f.read()))

    else:
        code = bytes.fromhex(strip_0x(args.code))

    print("\n".join(disassemble(code)))


if __name__ == "__main__":
    main()
