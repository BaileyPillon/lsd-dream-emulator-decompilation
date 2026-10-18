"""Fixed transport and opt-in selection for read-only primitive snapshots."""
from tools.replay_cold_start_headless import require
PC=0x8001F8B8
FUNCTION_BYTES=1944
EVENT_BYTES=988
RAM_BYTES=0x200000
FRAME_BYTES=0x800000
EXPORTS=('LsdResetCollisionCalls','LsdConfigureCollisionCalls','LsdStartCollisionCalls','LsdBeginCollisionCallFrame',
 'LsdGetCollisionCallCount','LsdGetCollisionCallTotal','LsdGetCollisionCallStarted','LsdGetCollisionCallEligible',
 'LsdGetCollisionCallOverflow','LsdGetCollisionCallPending','LsdGetCollisionCallDuplicateSkips',
 'LsdGetCollisionCallFrameSkips','LsdGetCollisionCallLimitSkips','LsdGetCollisionCallNestedSkips',
 'LsdGetCollisionCallDataBytes','LsdGetCollisionCallEvents','LsdGetCollisionCallData')
ORDINAL_EXPORTS=('LsdConfigureCollisionCallOrdinals','LsdGetCollisionCallOrdinalSkips')
CPU_FIELDS=tuple('gpr_'+str(i) for i in range(32))+('lo','hi','sr','cause','epc')
CONTEXT=('pc','ram','fetch','rs','sp','flags','sr')
FIELDS=('frame','ordinal','entry_id','base_ordinal','entry_frame','entry_timestamp','entry_pc','return_pc','timestamp',
 'entry_sequence_low','entry_sequence_high','sequence_low','sequence_high',
 *('entry_cpu_'+name for name in CPU_FIELDS),*('cpu_'+name for name in CPU_FIELDS),
 *('entry_gte_data_'+str(i) for i in range(32)),*('entry_gte_control_'+str(i) for i in range(32)),
 *('gte_data_'+str(i) for i in range(32)),*('gte_control_'+str(i) for i in range(32)),
 *(prefix+'_'+name for prefix in ('entry_jump','entry_delay','jump','delay') for name in CONTEXT),
 'ram_bytes','before_offset','after_offset','payload_status')
assert len(FIELDS)*4==EVENT_BYTES


def selection(program):
    trace=program.get('method_trace',{});config=trace.get('collision_calls')
    if config is None:return None
    require(isinstance(config,dict) and type(config.get('max_samples')) is int
            and 1<=config['max_samples']<=64,
            'Select 1..64 collision snapshots.')
    if set(config)=={'max_samples','per_key'}:
        require(type(config['per_key']) is int and config['per_key']==2,
                'Select exactly two snapshots per observed caller/model-address key.')
        policy=dict(per_key=2)
    else:
        require(set(config)=={'max_samples','ordinal_first','ordinal_step'}
                and type(config['ordinal_first']) is int and type(config['ordinal_step']) is int
                and 1<=config['ordinal_first']<=config['ordinal_step']<=64,
                'Ordinal selection requires an integer first and step with 1 <= first <= step <= 64.')
        policy=dict(ordinal_first=config['ordinal_first'],ordinal_step=config['ordinal_step'])
    require(trace.get('range_family')=='collision' and trace.get('targets')==['func_8001DDF4','func_8001F8B8']
            and not trace.get('flow_sites') and not trace.get('return_trace') and not trace.get('sdk_reads'),
            'Collision snapshots require the declared entry-only collision family.')
    return dict(pc=PC,bytes=FUNCTION_BYTES,max_samples=config['max_samples'],**policy)
