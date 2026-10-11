"""Run each legacy compiler stage with arguments and propagate every failure."""

import subprocess
import sys

STAGES = ("--cpp", "--cc", "--maspsx", "--as")


def parse_stages(arguments):
    commands = []
    for index, marker in enumerate(STAGES):
        if not arguments or arguments[0] != marker:
            raise ValueError(f"Expected {marker} compiler stage.")
        arguments = arguments[1:]
        boundary = arguments.index(STAGES[index + 1]) if index + 1 < len(STAGES) else len(arguments)
        command, arguments = arguments[:boundary], arguments[boundary:]
        if not command:
            raise ValueError(f"Empty {marker} compiler stage.")
        commands.append(command)
    return commands


def run_stages(commands):
    data = None
    for command in commands:
        data = subprocess.run(command, input=data, stdout=subprocess.PIPE, check=True).stdout
    return data


def main(arguments=None):
    try:
        output = run_stages(parse_stages(sys.argv[1:] if arguments is None else arguments))
        if output:
            sys.stdout.buffer.write(output)
        return 0
    except subprocess.CalledProcessError as error:
        print(f"Compiler stage failed ({error.returncode}): {error.cmd[0]}", file=sys.stderr)
        return error.returncode if error.returncode > 0 else 1
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
