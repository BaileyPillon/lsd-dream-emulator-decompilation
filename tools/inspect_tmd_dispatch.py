"""Locate original TMD streams that this specific draw entry returns from.

This is static source-data inspection, not native execution or proof that a
model is unused. Tag-nonzero LBD grid references remain separate from runtime
selection, visibility, caller attributes, transforms and actual draw routing.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path,PurePosixPath
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.disc_files import Mode2Disc,require
from tools.inventory_animations import lbd_info
from tools.inventory_model_packets import file_sha
from tools.psx_image import EXECUTABLE_NAME,ORIGINAL_SHA1
from tools.tmd_packets import geometries,model_ranges,packets
from tools.tmd_renderer_model import FORMATS
from tools.verify_model_packets import write_json


def dispatch_summary(records):
    """Predict the first unsupported run using the original FD07 header mask."""
    formats=Counter()
    unsupported=[]
    for ordinal,packet in enumerate(records):
        formats[f'0x{packet.mode:02x}/0x{packet.flags:02x}']+=1
        if (packet.mode&0xFD,packet.flags&7) not in FORMATS:unsupported.append(ordinal)
    count=sum(formats.values())
    return dict(source_packets=count,source_formats=dict(formats),unsupported_packets=len(unsupported),
        first_unsupported_ordinal=unsupported[0] if unsupported else None,
        predicted_primitive_setup_calls=unsupported[0] if unsupported else count,
        predicted_unvisited_tail_packets=count-unsupported[0] if unsupported else 0)


def inspect(disc_path,inventory_path):
    require(0<inventory_path.stat().st_size<=4*1024**2,'Use a bounded existing model inventory.')
    inventory=json.loads(inventory_path.read_bytes())
    require(inventory.get('status')=='model_vertex_references_verified' and inventory.get('unresolved')==[],
        'Use a complete static model inventory.')
    names=('tools/inspect_tmd_dispatch.py','tools/tmd_renderer_model.py','tools/tmd_packets.py',
        'tools/disc_files.py','tools/inventory_animations.py','tools/inventory_model_packets.py',
        'tools/psx_image.py','tools/verify_model_packets.py')
    sources={name:file_sha(ROOT/name) for name in names}
    for name,digest in inventory['source_dependencies'].items():
        path=(ROOT/name.replace('\\','/')).resolve()
        require(path.is_relative_to(ROOT) and file_sha(path)==digest,'Static inventory dependency differs: '+name)
    rows,counts=[],Counter()
    with Mode2Disc(disc_path) as disc:
        before=disc.path.stat()
        require(file_sha(disc.path)==inventory['raw_disc_sha256'],'Original disc hash differs.')
        files=disc.files()
        selected={name:record for name,record in files.items()
            if PurePosixPath(name).suffix in ('.LBD','.MOM','.TMD')}
        require(set(selected)=={row['path'] for row in inventory['rows']},'Model file set differs.')
        require(hashlib.sha1(disc.read_file(files['/'+EXECUTABLE_NAME])).hexdigest()==ORIGINAL_SHA1,
            'Canonical original executable differs.')
        for source in inventory['rows']:
            data=disc.read_file(selected[source['path']])
            require(len(data)==source['bytes'] and hashlib.sha256(data).hexdigest()==source['sha256'],
                'Original model bytes differ.')
            level=lbd_info(data) if PurePosixPath(source['path']).suffix=='.LBD' else None
            for model in model_ranges(data,PurePosixPath(source['path']).suffix):
                counts['TMD_tables']+=1
                for geometry in geometries(data,model['tmd'],model['limit']):
                    summary=dispatch_summary(packets(data,geometry))
                    counts.update(objects=1,source_packets=summary['source_packets'])
                    if not summary['unsupported_packets']:continue
                    refs=level['present_model_indices'].get(str(geometry.index),0) if model['kind']=='LBD' else None
                    rows.append(dict(path=source['path'],source_sha256=source['sha256'],kind=model['kind'],
                        tmd=model['tmd'],object=geometry.index,grid_present_record_references=refs,**summary))
                    counts.update(objects_with_unsupported_formats=1,unsupported_source_packets=summary['unsupported_packets'],
                        predicted_unvisited_tail_packets=summary['predicted_unvisited_tail_packets'])
                    if refs is not None:
                        counts['grid_referenced_objects' if refs else 'grid_unreferenced_objects']+=1
                        counts['grid_present_record_references']+=refs
        after=disc.path.stat()
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and
            file_sha(disc.path)==inventory['raw_disc_sha256'],'Original disc changed during inspection.')
    require(sources=={name:file_sha(ROOT/name) for name in names},'Inspection sources changed.')
    return dict(schema_version=1,status='static_original_draw_dispatch_routes_inspected',
        generated_at=datetime.now(timezone.utc).isoformat(),raw_disc_sha256=inventory['raw_disc_sha256'],
        inventory_sha256=file_sha(inventory_path),canonical_executable_sha1=ORIGINAL_SHA1,
        source_sha256=sources,counts=dict(counts),rows=rows,
        dispatch_entry='0x80018464',dispatch_header_mask='0xfd07',
        reference_scope='All bounded tag-nonzero records in the native primary LBD tile grid, including additional records.',
        original_native_execution_performed=False,natural_game_draw_routes_verified=False,
        unused_or_collision_only_roles_proven=False,asset_payloads_extracted=False,
        original_assets_or_game_source_modified=False,new_matching_C_bytes=0,whole_feature_groups_accepted=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        require(not args.output.exists(),'Choose a fresh dispatch report path.')
        report=inspect(args.disc,args.inventory)
        write_json(args.output,report)
        print(json.dumps(dict(status=report['status'],counts=report['counts'])))
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='invalid_dispatch_inspection',error=str(error))),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
