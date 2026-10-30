"""Count retained capture bytes without following shared runtime links.

This is a logical output bound, separate from physical disk-allocation audits.
Concurrent replacement of a temporary status file may remove it during a scan.
"""
import os
from pathlib import Path
import stat


def owned_output_bytes(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    pending = [root]
    total = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    pending.append(entry.path)
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
    return total
