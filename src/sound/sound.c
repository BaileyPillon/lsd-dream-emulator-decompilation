#include <psx/libsnd.h>

#include "base/base.h"
#include "scene/entity.h"
#include "sound/sound.h"
#include <psx/libspu.h>

/* VAB loading, SDK note dispatch and shared SPU ownership. File-driver phases
 * and note/voice ordering mirror the original asynchronous implementation. */
extern sound_vtable_t g_SOUND_VTABLE;

extern s32 g_SoundInstanceCount;
extern s32 g_CrescendoTimeMod;
extern s32 g_SpuInitialized;
extern s32 g_SndEngineInitialized;
extern s32 g_MasterVolumeSet;
extern char g_VabHeaderExt[];
extern s32 g_VabHeaderPtr;
extern char g_VabBodyExt[];

void *get_file_driver(void);
s32 bgm_is_active(void);
s32 bgm_get_sequence_work(void);
void func_800329D8(void);
void func_80032A7C(void);
void func_800323A8(s32, s32, s32);
void func_80032588(s32);
void build_data_path(char *, char *, char *, char *);
extern char *strcpy(char *, char *);
extern s32 strlen(char *);
s16 func_80030E90(s16, s16, s16, s16, s32, s32, s32);
extern s16 SsUtGetVabHdr(s16, void *);
extern s16 SsUtGetProgAtr(s16, s16, u8 *);
extern s16 SsUtGetVagAtr(s16, s16, s16, u8 *);
extern void SsSetMVol(s16, s16);

sound_t *sound_create(u32 PathAddress) {
    sound_t *allocated = ALLOCATE_STRUCT(sound_t);

    if (allocated) {
        sound_get_vtable()->sound_construct(allocated, PathAddress);
        return allocated;
    }

    return NULL;
}

void sound_construct(sound_t *This, char *Path) {
    char path_buffer[0x20];
    char *owned_path;

    (*(void (**)(sound_t *))((s32) get_file_driver() + 8))(This);
    This->vtable = sound_get_vtable();
    This->m_ToneStorage = 0;
    This->m_ProgramTable = 0;
    This->m_VabId = 0;
    This->m_IsMuted = 0;
    This->vtable->sound_set_volume_offset(This, 0);
    This->m_VabReady = 0;
    This->m_TransferPending = 0;
    This->m_PathStorage = 0;
    if (g_SpuInitialized == 0) {
        SpuInit();
        g_SpuInitialized = 1;
        func_800323A8(bgm_get_sequence_work(), 2, 1);
    }
    if (g_SndEngineInitialized == 0) {
        g_CrescendoTimeMod = 0x3C;
        func_80032588(1);
        g_SndEngineInitialized = 1;
    }
    g_SoundInstanceCount += 1;
    /* Keep the path alive until the header load schedules the matching body. */
    if (Path != 0) {
        owned_path = (char *) memory_allocate_mem(strlen(Path) + 1);
        if (owned_path != 0) {
            This->m_PathStorage = (s32) owned_path;
            strcpy(owned_path, Path);
            build_data_path(path_buffer, owned_path, NULL, g_VabHeaderExt);
            This->unk10_2 = 1;
            This->vtable->Unk11(This, path_buffer);
        }
    }
}

void sound_close(sound_t *This) {
    s32 count;

    SsVabClose(This->m_VabId);
    count = g_SoundInstanceCount - 1;
    g_SoundInstanceCount = count;
    if (count < 0) {
        g_SoundInstanceCount = 0;
    }
    if ((g_SoundInstanceCount == 0) && (bgm_is_active() == 0)) {
        g_SpuInitialized = 0;
        g_MasterVolumeSet = 0;
        g_SndEngineInitialized = 0;
        func_800329D8();
        func_80032A7C();
    }
    memory_free_mem((void *) This->m_ToneStorage);
    memory_free_mem((void *) This->m_ProgramTable);
    memory_free_mem((void *) This->m_PathStorage);
    (*(void (**)(sound_t *))((s32) get_file_driver() + 0xC))(This);
}

void sound_update_vab_load(sound_t *This) {
    char path_buffer[0x20];
    s32 header_address;
    s16 vab_id;
    s32 load_phase;

    load_phase = This->unk10_2;
    if (load_phase == 1) {
        goto case1;
    }
    if (load_phase < 2) {
        goto done;
    }
    if (load_phase == 6) {
        goto case6;
    }
    goto done;

case1:
    if (This->m_FlagsUnk & 0x200) {
        This->m_VabId = SsVabOpenHead((unsigned char *) This->unk4, -1);
        build_data_path(path_buffer, (char *) This->m_PathStorage, NULL, g_VabBodyExt);
        header_address = This->unk4;
        This->unk10_2 = 6;
        This->unk4 = 0;
        g_VabHeaderPtr = header_address;
        This->vtable->Unk6(This, path_buffer);
        if (This->m_PathStorage != 0) {
            memory_free_mem((void *) This->m_PathStorage);
            This->m_PathStorage = 0;
        }
    }
    goto done;
case6:
    if (This->m_FlagsUnk & 0x200) {
        vab_id = SsVabTransBody((unsigned char *) This->unk4, This->m_VabId);
        This->m_VabId = vab_id;
        if (vab_id != -1) {
            This->m_TransferPending = 1;
            This->vtable->sound_finish_vab_load(This, 1);
        }
    }
done:
    return;
}

s32 sound_finish_vab_load(sound_t *This, s32 WaitForTransfer) {
    s32 return_value = 0;

    if (This->m_TransferPending) {

        if (WaitForTransfer) {
            SsVabTransCompleted(1);
            This->m_TransferPending = 0;
            This->m_VabReady = 1;

            This->vtable->sound_build_program_table(This);
            return_value = 1;
        }
    }

    return return_value;
}

void sound_build_program_table(sound_t *This) {
    u8 program_attributes[0x10];
    u8 *cursor;
    u8 *program_table;
    u8 *tone_storage;
    s32 program_index;
    s32 tone_index;

    if (This->m_VabReady != 0) {
        This->vtable->file_buf_release(This);
        This->unk4 = g_VabHeaderPtr;
        if (SsUtGetVabHdr(This->m_VabId, (u8 *)This + 0x2C) != -1) {
            tone_storage = (u8 *)memory_allocate_mem(*(u16 *)((u8 *)This + 0x40) << 5);
            This->m_ToneStorage = (s32)tone_storage;
            if (tone_storage != 0) {
                program_table = (u8 *)memory_allocate_mem(*(u16 *)((u8 *)This + 0x3E) << 2);
                This->m_ProgramTable = (s32)program_table;
                if (program_table != 0) {
                    cursor = (u8 *)This->m_ToneStorage;
                    program_index = 0;
                    if (program_index < (s32)*(u16 *)((u8 *)This + 0x3E)) {
                        do {
                            *(u32 *)(This->m_ProgramTable + program_index * 4) = (u32)cursor;
                            if (SsUtGetProgAtr(This->m_VabId, program_index, program_attributes) == -1) {
                                return;
                            }
                            tone_index = 0;
                            if (tone_index < (s32)program_attributes[0]) {
                                do {
                                    if (SsUtGetVagAtr(This->m_VabId, program_index, (s16)tone_index, cursor) == -1) {
                                        return;
                                    }
                                    tone_index++;
                                    cursor += 0x20;
                                } while (tone_index < (s32)program_attributes[0]);
                            }
                            program_index++;
                        } while (program_index < *(u16 *)((u8 *)This + 0x3E));
                    }
                    if (g_MasterVolumeSet == 0) {
                        func_80032998();
                        SsSetMVol(0x78, 0x78);
                        g_MasterVolumeSet = 1;
                    }
                }
            }
        }
    }
}

s16 sound_play_note(sound_t *This, s32 NoteIndex, s16 Volume, s16 TargetVolume) {
    s32 program_index;
    u8 *tone_attributes;
    s16 voice;

    if (NoteIndex >= 0) {
        program_index = NoteIndex >> 4;
        tone_attributes = *(u8 **) (This->m_ProgramTable + program_index * 4);
        tone_attributes += (NoteIndex - (program_index << 4)) * 32;
        voice = func_80030E90(This->m_VabId,
                             (s16) program_index,
                             (s16) (NoteIndex - (program_index << 4)),
                             (s16) (tone_attributes[4] + (u16) This->m_PitchOffset),
                             tone_attributes[5], Volume, Volume);
        if (voice >= 0) {
            SsUtAutoVol(voice, Volume, TargetVolume, 2);
            return voice;
        }
    }
    return -1;
}

s32 sound_stop_note(void *This, s32 Voice) {
    if (Voice < 24) {
        func_80031890((s16) Voice);
    } else {
        func_80031F3C((s16) 0);
    }
    return -1;
}

void sound_mute(sound_t *This) {
    if (!This->m_IsMuted) {
        SsSetMute(SS_MUTE_ON);
        This->m_IsMuted = 1;
    }
}

void sound_unmute(sound_t *This) {
    if (This->m_IsMuted) {
        SsSetMute(SS_MUTE_OFF);
        This->m_IsMuted = 0;
    }
}

void sound_nop_1(void) {
}

void sound_nop_2(void) {
}

void sound_nop_3(void) {
}

void sound_set_volume_offset(sound_t *This, s32 Octave) {
    /* The inherited name is misleading: this is a semitone pitch offset. */
    This->m_PitchOffset = 12 * Octave - 24;
}

sound_vtable_t *sound_get_vtable(void) {
    return &g_SOUND_VTABLE;
}

s32 sound_get_instance_count(void) {
    return g_SoundInstanceCount;
}

s32 sound_get_crescendo_time_mod(void) {
    return g_CrescendoTimeMod;
}

s32 sound_entity_init(sound_t *This, s32 *Unk2, s32 Unk3, s32 Unk4, s32 Unk5) {
    s32 *ptr;
    s32 val;
    s32 i;

    if (*Unk2 != 0) {
        return 0;
    }

    ptr = Unk2 + 6;
    val = -1;
    i = 2;

    Unk2[0] = Unk3;
    Unk2[2] = Unk4;
    Unk2[3] = Unk5;

    do {
        *ptr = val;
        i--;
        ptr += 5;
    } while (i >= 0);

    Unk2[1] = 0;
    Unk2[5] = 10;

    return 1;
}

void sound_entity_stop(void **This, s32 *Unk2) {
    s32 *ptr;
    s32 i;
    s32 val;

    ptr = Unk2 + 6;
    i = 0;
    do {
        val = *ptr;
        i += 1;
        if (val >= 0) {
            *ptr = (*(s32(**)(void **, s32))(*(u32 *) This + 0x84))(This, val);
        }
        ptr += 5;
    } while (i < 3);
    *Unk2 = 0;
}

void sound_entity_update(sound_t *This, entity_context_t *Unk2) {
    entity_effect_slot_t *slot;
    entity_effect_slot_t *init;
    s32 i;

    if (Unk2->state > 0) {
        i = 0;
        init = Unk2->slots;
        do {
            i += 1;
            init->id = -1;
            init->param = 0;
            init->period = 0x7F;
            init->counter = 0x40;
            init += 1;
        } while (i < 3);

        Unk2->motion = 0;
        if (Unk2->callback != NULL) {
            Unk2->callback(Unk2->owner, (s32 *) Unk2);
        }

        if (Unk2->motion >= 0) {
            slot = Unk2->slots;
            i = 0;
            do {
                if (slot->id >= 0) {
                    if (slot->handle >= 0) {
                        This->vtable->sound_stop_note(This, slot->handle);
                    }
                    This->vtable->sound_set_volume_offset(This, slot->param);
                    slot->handle = This->vtable->sound_play_note(
                        This, slot->id << 4, slot->period - (slot->period / Unk2->divisor) * Unk2->motion,
                        slot->counter - (slot->counter / Unk2->divisor) * Unk2->motion);
                } else if (slot->id == -2) {
                    if (slot->handle >= 0) {
                        This->vtable->sound_stop_note(This, slot->handle);
                    }
                }
                i += 1;
                slot += 1;
            } while (i < 3);
        }
        Unk2->tick += 1;
    }
}
