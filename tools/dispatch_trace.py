"""Static controller and complete-target checks for the separate method recorder."""
import csv
import hashlib
import io
import re
import struct
from tools.record_npc_history import clean_name, digest_text
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require
from research.compiler.compare_function import CANONICAL_SHA256


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_program(program):
    require(isinstance(program, dict) and program.get('schema_version') == 1, 'Unsupported controller program schema.')
    frames = program.get('frames')
    require(type(frames) is int and 1 <= frames <= 30000, 'The controller program supports 1 through 30000 input frames.')
    require(digest_text(program.get('executable_sha256')) and digest_text(program.get('disc_track_sha256')),
            'The program must identify its canonical executable and complete disc track.')
    controller = program.get('controller', {})
    buttons, axes, order = (controller.get(name) for name in ('buttons', 'axes', 'column_order'))
    require(isinstance(buttons, list) and buttons and all(clean_name(name) for name in buttons)
            and len(buttons) == len(set(buttons)), 'Button names must be unique nonempty TSV fields.')
    require(isinstance(axes, dict) and all(clean_name(name) and type(value) is int and -(2**31) <= value < 2**31
                                         for name, value in axes.items()), 'Invalid neutral controller axes.')
    require(not set(buttons) & set(axes) and isinstance(order, list) and all(clean_name(name) for name in order)
            and len(order) == len(set(order)) and set(order) == set(buttons) | set(axes),
            'Controller columns must name each button and axis exactly once.')
    segments = program.get('segments')
    require(isinstance(segments, list) and segments, 'The controller program needs contiguous input segments.')
    previous = 0
    for segment in segments:
        require(isinstance(segment, dict), 'Invalid controller segment.')
        until, phase, pressed = (segment.get(name) for name in ('until', 'phase', 'pressed'))
        require(type(until) is int and previous < until <= frames and clean_name(phase),
                'Input segments must advance consecutively to the declared final frame.')
        require(isinstance(pressed, list) and all(isinstance(name, str) for name in pressed)
                and len(pressed) == len(set(pressed)) and set(pressed) <= set(buttons),
                'A segment contains an unknown or repeated button.')
        previous = until
    require(previous == frames, 'Input segments do not cover the complete program.')
    checkpoints = program.get('checkpoint_frames')
    require(isinstance(checkpoints, list) and 2 <= len(checkpoints) <= 256
            and all(type(frame) is int and 0 <= frame <= frames for frame in checkpoints)
            and checkpoints == sorted(set(checkpoints)) and checkpoints[0] == 0 and checkpoints[-1] == frames,
            'Use sorted unique checkpoint frames, including zero and the final frame, with at most 256 captures.')
    interval = program.get('RAM_sample_interval')
    require(type(interval) is int and 1 <= interval <= frames, 'Invalid RAM observation interval.')
    trace = program.get('method_trace', {})
    names = trace.get('targets')
    require(isinstance(names, list) and 1 <= len(names) <= 16
            and all(isinstance(name,str) and re.fullmatch(r'[A-Za-z_]\w*',name) for name in names)
            and len(set(names)) == len(names),
            'Select one through sixteen unique declared method names.')
    require(type(trace.get('arm_frame')) is int and 0 <= trace['arm_frame'] <= frames,
            'The method observer arm frame lies outside the program.')
    words = trace.get('memory_symbols')
    require(isinstance(words,list) and len(words)==4
            and all(isinstance(name,str) and re.fullmatch(r'[A-Za-z_]\w*',name) for name in words)
            and len(set(words))==4,
            'Select exactly four unique original memory symbols.')
    if 'expanded_submitted_sha256' in program:
        require(digest_text(program['expanded_submitted_sha256']),'Invalid expanded-input checksum.')
    return program


def expand_program(program, frames=None):
    program = validate_program(program)
    frames = program['frames'] if frames is None else frames
    require(type(frames) is int and 1 <= frames <= program['frames'], 'Choose an input window within the controller program.')
    controller = program['controller']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(('relative_frame', 'core_frame', 'phase', 'buttons', *controller['column_order']))
    segment_index = 0
    for frame in range(1, frames + 1):
        while frame > program['segments'][segment_index]['until']:
            segment_index += 1
        segment = program['segments'][segment_index]
        pressed = set(segment['pressed'])
        summary = ';'.join(name for name in controller['buttons'] if name in pressed)
        values = [('true' if name in pressed else 'false') if name in controller['buttons'] else str(controller['axes'][name])
                  for name in controller['column_order']]
        writer.writerow((frame, frame, segment['phase'], summary, *values))
    data = stream.getvalue().encode('utf-8')
    if frames == program['frames'] and 'expanded_submitted_sha256' in program:
        require(sha256(data) == program['expanded_submitted_sha256'], 'Expanded controller inputs differ from the recorded program checksum.')
    return data


def verified_selection(program, catalogue, provenance, catalogue_raw, executable,
                       supplemental=None, supplemental_provenance=None, supplemental_raw=None):
    require(hashlib.sha256(executable).hexdigest()==CANONICAL_SHA256==program['executable_sha256'],
            'Require the canonical original executable for method selection.')
    require(catalogue.get('schema_version')==1 and catalogue.get('kind')=='original_LSD_declared_dispatch_targets'
            and catalogue.get('canonical_executable_sha256')==CANONICAL_SHA256,
            'Unsupported original dispatch catalogue.')
    require(hashlib.sha256(catalogue_raw).hexdigest()==provenance.get('catalogue',{}).get('sha256')
            and provenance.get('status')=='verified_complete_declared_dispatch_catalogue',
            'Dispatch catalogue bytes differ from their published provenance.')
    targets=catalogue.get('targets')
    require(isinstance(targets,list) and len(targets)==provenance.get('complete_target_function_ranges'),
            'Incomplete original dispatch catalogue.')
    by_name={row['function']:row for row in targets}
    require(len(by_name)==len(targets),'Ambiguous original target function names.')
    owners={int(row['pc'],16):row['function'] for row in targets}
    require(len(owners)==len(targets),'Ambiguous original target function addresses.')
    if supplemental is not None:
        require(supplemental_provenance is not None and supplemental_raw is not None
                and supplemental_provenance.get('status')=='verified_bounded_file_driver_interface_repair'
                and supplemental_provenance.get('canonical_executable_sha256')==CANONICAL_SHA256
                and supplemental_provenance.get('original_symbol_diagnostic',{}).get('complete_canonical_image_equal') is True
                and supplemental_provenance.get('original_symbol_diagnostic',{}).get('independent_GNU_sized_function_extents_equal') is True,
                'Supplemental method ranges need their complete canonical ELF/GNU qualification.')
        require(hashlib.sha256(supplemental_raw).hexdigest()==supplemental_provenance.get('producer_dependencies',{}).get(
                    'research/file_driver/function-ranges.json')
                and isinstance(supplemental,list) and len(supplemental)==supplemental_provenance.get('original_function_range_count'),
                'Supplemental range bytes differ from their published provenance.')
        names=set()
        for record in supplemental:
            name=record['function']
            require(name not in names,'Ambiguous supplemental function name.')
            names.add(name)
            pc,length=int(record['address'],16),record['bytes']
            require(owners.get(pc,name)==name,'Declared and supplemental function owners disagree.')
            owners[pc]=name
            start=executable_offset(executable,pc,length)
            code=executable[start:start+length]
            require(hashlib.sha256(code).hexdigest()==record['sha256'],'Complete supplemental method differs from original.')
            row=dict(function=name,pc=f'0x{pc:08X}',function_bytes=length,function_sha256=record['sha256'],
                entry_instruction_sha256=hashlib.sha256(code[:4]).hexdigest(),
                range_source='file_driver_interface_ranges',bindings=[item for item in
                    supplemental_provenance.get('original_slot_bindings',[]) if item['function']==name])
            if name in by_name:
                require(all(row[key]==by_name[name][key] for key in
                    ('pc','function_bytes','function_sha256','entry_instruction_sha256')),
                    'Declared and supplemental method ownership disagree.')
            else:
                by_name[name]=row
    selected={}
    for name in program['method_trace']['targets']:
        require(name in by_name,'Selected method is absent from the declared catalogue: '+name)
        row=by_name[name]
        pc,length=int(row['pc'],16),row['function_bytes']
        require(0x80010000<=pc<0x80200000 and pc%4==0 and type(length) is int
                and 0<length<=4096 and length%4==0 and pc not in selected,
                'Selected methods require complete unique spans of at most 4096 bytes.')
        start=executable_offset(executable,pc,length)
        code=executable[start:start+length]
        require(hashlib.sha256(code).hexdigest()==row['function_sha256']
                and hashlib.sha256(code[:4]).hexdigest()==row['entry_instruction_sha256'],
                'Complete selected method differs from the original: '+name)
        selected[pc]=row
    return selected
