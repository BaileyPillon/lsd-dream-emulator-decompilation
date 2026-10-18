// Optional sampled collision call/return snapshots. Original CPU/GTE/RAM are read-only.
#ifndef LSD_COLLISION_CALL_OBSERVER_H
#define LSD_COLLISION_CALL_OBSERVER_H
#include "dispatch_entry_observer.h"
#include "mednafen/src/psx/gte.h"

struct LsdCollisionContext { uint32_t pc, ram, fetch, rs, sp, flags, sr; };
struct LsdCollisionCall {
    uint32_t frame, ordinal, entry_id, base_ordinal, entry_frame;
    int32_t entry_timestamp;
    uint32_t entry_pc, return_pc;
    int32_t timestamp;
    uint32_t entry_sequence_low, entry_sequence_high, sequence_low, sequence_high;
    uint32_t entry_cpu[37], cpu[37]; // GPR0..31, LO, HI, SR, CAUSE, EPC.
    uint32_t entry_gte_data[32], entry_gte_control[32], gte_data[32], gte_control[32];
    LsdCollisionContext entry_jump, entry_delay, jump, delay;
    uint32_t ram_bytes, before_offset, after_offset, payload_status;
};
static_assert(sizeof(LsdCollisionCall)==988,"Collision call transport layout");
struct LsdCollisionKey { uint32_t caller, model, count; };
static LsdCollisionCall lsd_collision_pending, lsd_collision_events[2];
static uint8_t lsd_collision_before[0x200000], lsd_collision_data[0x800000], lsd_collision_windows[524288];
static LsdCollisionKey lsd_collision_keys[64];
static LsdCollisionContext lsd_collision_previous, lsd_collision_before_previous;
static uint32_t lsd_collision_count, lsd_collision_total, lsd_collision_started, lsd_collision_eligible;
static uint32_t lsd_collision_overflow, lsd_collision_data_bytes, lsd_collision_key_count;
static uint32_t lsd_collision_duplicates, lsd_collision_frame_skips, lsd_collision_limit_skips, lsd_collision_nested_skips;
static uint32_t lsd_collision_ordinal_first, lsd_collision_ordinal_step, lsd_collision_ordinal_skips;
static uint32_t lsd_collision_pc, lsd_collision_bytes, lsd_collision_limit, lsd_collision_start_frame;
static uint64_t lsd_collision_sequence;
static bool lsd_collision_active;

static void LsdCollisionRegisters(uint32_t* cpu,uint32_t* data,uint32_t* control) {
    for(unsigned i=0;i<32;++i) {
        cpu[i]=CPU->GetRegister(i,NULL,0); data[i]=GTE_ReadDR(i); control[i]=GTE_ReadCR(i);
    }
    const unsigned extra[5]={PS_CPU::GSREG_LO,PS_CPU::GSREG_HI,PS_CPU::GSREG_SR,PS_CPU::GSREG_CAUSE,PS_CPU::GSREG_EPC};
    for(unsigned i=0;i<5;++i) cpu[32+i]=CPU->GetRegister(extra[i],NULL,0);
}
static void LsdCollisionFinish(uint32_t pc,pscpu_timestamp_t timestamp) {
    if(lsd_collision_count==2 || sizeof(lsd_collision_data)-lsd_collision_data_bytes<0x400000) {
        ++lsd_collision_overflow;lsd_collision_active=false;return;
    }
    LsdCollisionCall& e=lsd_collision_events[lsd_collision_count++];e=lsd_collision_pending;
    e.frame=lsd_dispatch_frame;e.ordinal=++lsd_collision_total;e.return_pc=pc;e.timestamp=timestamp;
    e.sequence_low=(uint32_t)lsd_collision_sequence;e.sequence_high=(uint32_t)(lsd_collision_sequence>>32);
    LsdCollisionRegisters(e.cpu,e.gte_data,e.gte_control);
    e.jump=lsd_collision_before_previous;e.delay=lsd_collision_previous;
    e.ram_bytes=0x200000;e.before_offset=lsd_collision_data_bytes;e.after_offset=e.before_offset+0x200000;e.payload_status=1;
    memcpy(lsd_collision_data+e.before_offset,lsd_collision_before,0x200000);
    memcpy(lsd_collision_data+e.after_offset,MainRAM.data8,0x200000);lsd_collision_data_bytes+=0x400000;
    lsd_collision_active=false;
}
static void LsdCollisionPush(pscpu_timestamp_t timestamp) {
    ++lsd_collision_eligible;
    if(lsd_collision_ordinal_step && (lsd_collision_eligible<lsd_collision_ordinal_first ||
       (lsd_collision_eligible-lsd_collision_ordinal_first)%lsd_collision_ordinal_step)) {
        ++lsd_collision_ordinal_skips;return;
    }
    if(lsd_collision_active) {++lsd_collision_nested_skips;return;}
    if(lsd_collision_started==lsd_collision_limit) {++lsd_collision_limit_skips;return;}
    const uint32_t caller=lsd_collision_before_previous.pc,model=CPU->GetRegister(4,NULL,0);
    unsigned key=0;
    if(!lsd_collision_ordinal_step) {
        for(;key<lsd_collision_key_count;++key)
            if(lsd_collision_keys[key].caller==caller && lsd_collision_keys[key].model==model) break;
        if(key<lsd_collision_key_count && lsd_collision_keys[key].count==2) {++lsd_collision_duplicates;return;}
    }
    if(lsd_collision_start_frame==lsd_dispatch_frame) {++lsd_collision_frame_skips;return;}
    if(!lsd_collision_ordinal_step) {
        if(key==lsd_collision_key_count) {
            if(key==64) {++lsd_collision_overflow;return;}
            lsd_collision_keys[key]={caller,model,0};++lsd_collision_key_count;
        }
        ++lsd_collision_keys[key].count;
    }
    lsd_collision_start_frame=lsd_dispatch_frame;
    memset(&lsd_collision_pending,0,sizeof(lsd_collision_pending));
    LsdCollisionCall& e=lsd_collision_pending;
    e.entry_id=++lsd_collision_started;e.base_ordinal=lsd_dispatch_total;
    e.entry_frame=lsd_dispatch_frame;e.entry_timestamp=timestamp;e.entry_pc=lsd_collision_pc;
    e.entry_sequence_low=(uint32_t)lsd_collision_sequence;e.entry_sequence_high=(uint32_t)(lsd_collision_sequence>>32);
    LsdCollisionRegisters(e.entry_cpu,e.entry_gte_data,e.entry_gte_control);
    e.entry_jump=lsd_collision_before_previous;e.entry_delay=lsd_collision_previous;
    memcpy(lsd_collision_before,MainRAM.data8,0x200000);lsd_collision_active=true;
}
static void LsdCollisionHook(const pscpu_timestamp_t timestamp,uint32_t pc) {
    ++lsd_collision_sequence;
    if(lsd_collision_active && pc==lsd_collision_pending.entry_cpu[31] &&
       CPU->GetRegister(29,NULL,0)==lsd_collision_pending.entry_cpu[29]) LsdCollisionFinish(pc,timestamp);
    LsdDispatchCpuEntry(timestamp,pc);
    if(pc==lsd_collision_pc) LsdCollisionPush(timestamp);
    LsdCollisionContext current={};current.pc=pc;
    if(!(pc&3) && pc>=0x80010000 && pc<0x80200000 &&
       (lsd_collision_active || lsd_collision_windows[(pc-0x80000000)>>2])) {
        current.ram=LsdDispatchRead(pc);current.fetch=current.ram;current.flags=1;
        if(CPU->PeekCheckICache(pc,&current.fetch)) current.flags|=2;
        current.rs=CPU->GetRegister((current.fetch>>21)&31,NULL,0);
        current.sp=CPU->GetRegister(29,NULL,0);current.sr=CPU->GetRegister(PS_CPU::GSREG_SR,NULL,0);
    }
    lsd_collision_before_previous=lsd_collision_previous;lsd_collision_previous=current;
}
ECL_EXPORT int LsdResetCollisionCalls() {
    lsd_collision_count=lsd_collision_total=lsd_collision_started=lsd_collision_eligible=0;
    lsd_collision_overflow=lsd_collision_data_bytes=lsd_collision_key_count=0;
    lsd_collision_duplicates=lsd_collision_frame_skips=lsd_collision_limit_skips=lsd_collision_nested_skips=0;
    lsd_collision_ordinal_first=lsd_collision_ordinal_step=lsd_collision_ordinal_skips=0;
    lsd_collision_pc=lsd_collision_bytes=lsd_collision_limit=0;lsd_collision_start_frame=0xFFFFFFFF;
    lsd_collision_sequence=0;lsd_collision_active=false;lsd_collision_previous={};lsd_collision_before_previous={};
    memset(lsd_collision_windows,0,sizeof(lsd_collision_windows));return 1;
}
ECL_EXPORT int LsdConfigureCollisionCalls(uint32_t pc,uint32_t bytes,uint32_t limit) {
    if(!((pc==0x8001F8B8 && bytes==1944) || (pc==0x8001DDF4 && bytes==796)) ||
       !limit || limit>64) return 0;
    lsd_collision_pc=pc;lsd_collision_bytes=bytes;lsd_collision_limit=limit;
    lsd_collision_ordinal_first=lsd_collision_ordinal_step=0;
    for(uint32_t at=pc;at<pc+bytes;at+=4) lsd_collision_windows[(at-0x80000000)>>2]=1;
    for(uint32_t at=0x80010000;at<0x801FFFFC;at+=4) {
        const uint32_t word=LsdDispatchRead(at);
        const bool direct=word>>26==3 && (((word&0x03FFFFFF)<<2)|0x80000000)==pc;
        // JALR's target is known only at execution; retain its register and delay context.
        // A candidate window alone does not certify a transfer to the selected function.
        const bool indirect=(word&0xFC1FFFFF)==0x0000F809;
        if(direct || indirect) {
            lsd_collision_windows[(at-0x80000000)>>2]=1;lsd_collision_windows[(at+4-0x80000000)>>2]=1;
        }
    }
    return 1;
}
ECL_EXPORT int LsdConfigureCollisionCallOrdinals(uint32_t pc,uint32_t bytes,uint32_t limit,uint32_t first,uint32_t step) {
    if(!first || first>step || step>64 || !LsdConfigureCollisionCalls(pc,bytes,limit)) return 0;
    lsd_collision_ordinal_first=first;lsd_collision_ordinal_step=step;return 1;
}
ECL_EXPORT int LsdStartCollisionCalls() {
    if(!CPU || !lsd_collision_pc || !lsd_dispatch_target_count) return 0;
    CPU->SetCPUHook(LsdCollisionHook,NULL);return 1;
}
ECL_EXPORT void LsdBeginCollisionCallFrame() {lsd_collision_count=lsd_collision_data_bytes=0;}
ECL_EXPORT uint32_t LsdGetCollisionCallCount() {return lsd_collision_count;}
ECL_EXPORT uint32_t LsdGetCollisionCallTotal() {return lsd_collision_total;}
ECL_EXPORT uint32_t LsdGetCollisionCallStarted() {return lsd_collision_started;}
ECL_EXPORT uint32_t LsdGetCollisionCallEligible() {return lsd_collision_eligible;}
ECL_EXPORT uint32_t LsdGetCollisionCallOverflow() {return lsd_collision_overflow;}
ECL_EXPORT uint32_t LsdGetCollisionCallPending() {return lsd_collision_active?1:0;}
ECL_EXPORT uint32_t LsdGetCollisionCallDuplicateSkips() {return lsd_collision_duplicates;}
ECL_EXPORT uint32_t LsdGetCollisionCallFrameSkips() {return lsd_collision_frame_skips;}
ECL_EXPORT uint32_t LsdGetCollisionCallLimitSkips() {return lsd_collision_limit_skips;}
ECL_EXPORT uint32_t LsdGetCollisionCallNestedSkips() {return lsd_collision_nested_skips;}
ECL_EXPORT uint32_t LsdGetCollisionCallOrdinalSkips() {return lsd_collision_ordinal_skips;}
ECL_EXPORT uint32_t LsdGetCollisionCallDataBytes() {return lsd_collision_data_bytes;}
ECL_EXPORT const LsdCollisionCall* LsdGetCollisionCallEvents() {return lsd_collision_events;}
ECL_EXPORT const uint8_t* LsdGetCollisionCallData() {return lsd_collision_data;}
#endif
