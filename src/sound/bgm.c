#include "sound/bgm.h"

#include <psx/libsnd.h>

#include "base/base.h"
#include "sound/seq_file.h"
#include "sound/sound.h"

/* Sequence playback and asynchronous file/bank readiness. The original open
 * path reports success even when SsSeqOpen returns -1; retain that behavior. */
const char g_SeqOpenErrorFmt[0x2C] = "Seq Open error in WBgmHandleMonitorEvent";

s32 g_BgmActive = 0;

void bgm_construct(bgm_t *, s32, s32, s32);
void bgm_cleanup(bgm_t *);
void bgm_on_notify(bgm_t *, s32 **, s32);
void bgm_handle_event(bgm_t *, s32, s32);
void seq_play(bgm_t *);
void seq_stop(bgm_t *);
void seq_pause(bgm_t *);
void seq_resume(bgm_t *);
void seq_set_vol(bgm_t *, s16, s16);
void bgm_set_crescendo(bgm_t *, s16, s32);
void bgm_set_sequence(bgm_t *, s32);
void bgm_set_sound(bgm_t *, s32);

bgm_vtable_t g_BGM_VTABLE = {
    0x50,
    base_class_destructor,
    (void (*)(void *, s32, s32, s32)) bgm_construct,
    (void (*)(void *)) bgm_cleanup,
    base_class_attach,
    base_class_detach,
    base_class_detach_all,
    base_class_iter_children,
    base_class_add_parent,
    base_class_remove_parent,
    base_class_clear_parents,
    base_class_iter_parents,
    base_class_notify,
    base_class_nop,
    (void (*)(void *)) bgm_on_notify,
    NULL,
    (void (*)(void *, void **, s32)) bgm_handle_event,
    (void (*)(void *)) seq_play,
    (void (*)(void *)) seq_stop,
    (void (*)(void *)) seq_pause,
    (void (*)(void *)) seq_resume,
    (void (*)(void *)) seq_set_vol,
    (void (*)(void *)) bgm_set_crescendo,
    (void (*)(void *, s32)) bgm_set_sequence,
    (void (*)(void *, s32)) bgm_set_sound,
};

void *get_display(void);
void func_8003AE18(s16);

bgm_t *bgm_create(u32 SoundPathAddress, u32 SequencePathAddress, u32 AutoPlay) {
    bgm_t *allocated = ALLOCATE_STRUCT(bgm_t);

    if (allocated) {
        bgm_get_vtable()->bgm_construct(allocated, SoundPathAddress, SequencePathAddress, AutoPlay);
        return allocated;
    }

    return NULL;
}

void bgm_construct(bgm_t *This, s32 SoundPathAddress, s32 SequencePathAddress, s32 AutoPlay) {
    base_class_get_vtable()->Construct(This);
    This->vtable = bgm_get_vtable();

    This->m_Sound = 0;
    This->m_SeqFile = 0;
    This->m_SeqAccess = 0;
    This->m_OpenState = 0;
    This->m_Paused = 0;
    This->m_Playing = 0;
    This->m_AutoPlay = AutoPlay;

    g_BgmActive = 1;
    This->vtable->bgm_set_sequence(This, SequencePathAddress);
    This->vtable->bgm_set_sound(This, SoundPathAddress);
    This->vtable->Attach(This, get_display());
}

void bgm_cleanup(bgm_t *This) {
    g_BgmActive = 0;
    This->vtable->seq_stop(This);
    func_8003AE18(This->m_SeqAccess);

    if (This->m_Sound) {
        This->m_Sound->vtable->Destroy(This->m_Sound);
    }

    if (This->m_SeqFile) {
        (*(void (**)(s32))(*(u32 *) This->m_SeqFile + 4))(This->m_SeqFile);
    }

    This->vtable->Detach(This, get_display());
    base_class_get_vtable()->Cleanup(This);
}

void bgm_on_notify(bgm_t *This, s32 **Sender, s32 Code) {
    base_class_get_vtable()->OnNotify(This, Sender, Code);

    if ((**(u32 **) Sender & 0xF) == 1) {
        This->vtable->bgm_handle_event(This, Sender, Code);
    }
}

void bgm_handle_event(bgm_t *This, s32 SenderAddress, s32 Code) {
    if (Code == 2 && This->m_OpenState == 1 && seq_open(This)) {
        if (This->m_AutoPlay) {
            This->vtable->seq_play(This);
        }
    }
}

s32 seq_open(bgm_t *This) {
    sound_t *sound;
    s32 sequence_file_address;
    s16 sequence_id;

    sound = This->m_Sound;
    if (sound == NULL) {
        return 0;
    }
    sequence_file_address = This->m_SeqFile;
    if (sequence_file_address == 0) {
        return 0;
    }
    if (sound->m_VabReady == 0) {
        return 0;
    }
    if (*(s32 *) (sequence_file_address + 0x2C) == 0) {
        return 0;
    }
    sequence_id = SsSeqOpen(*(u32 *) (sequence_file_address + 0x10), sound->m_VabId);
    This->m_SeqAccess = sequence_id;
    if (sequence_id == -1) {
        printf(g_SeqOpenErrorFmt);
    }
    SsSeqSetVol(This->m_SeqAccess, 0x34, 0x34);
    This->m_OpenState = 2;
    return 1;
}

void seq_play(bgm_t *This) {
    if (!This->m_Playing) {
        SsSeqSetVol(This->m_SeqAccess, 52, 52);
        SsSeqPlay(This->m_SeqAccess, 1, 0);
        This->m_Playing = 1;
    }
}

void seq_stop(bgm_t *This) {
    if (This->m_Playing) {
        SsSeqStop(This->m_SeqAccess);
        func_8003AE18(This->m_SeqAccess);
        This->m_Playing = 0;
        This->m_OpenState = 0;
    }
}

void seq_pause(bgm_t *This) {
    if (!This->m_Paused) {
        SsSeqPause(This->m_SeqAccess);
        This->m_Paused = 1;
    }
}

void seq_resume(bgm_t *This) {
    if (This->m_Paused) {
        SsSeqReplay(This->m_SeqAccess);
        This->m_Paused = 0;
    }
}

void seq_set_vol(bgm_t *This, s16 Left, s16 Right) {
    SsSeqSetVol(This->m_SeqAccess, Left, Right);
}

void bgm_set_crescendo(bgm_t *This, s16 Volume, s32 Time) {
    SsSeqSetCrescendo(This->m_SeqAccess, Volume, sound_get_crescendo_time_mod() * Time);
}

void bgm_set_sequence(bgm_t *This, s32 SequencePathAddress) {
    s32 previous_sequence_address;

    if (This->m_Playing) {
        This->vtable->seq_stop(This);
    }

    previous_sequence_address = This->m_SeqFile;
    if (previous_sequence_address) {
        (*(void (**)(int))(*(u32 *) previous_sequence_address + 4))(previous_sequence_address);
        This->m_SeqFile = 0;
    }
    if (SequencePathAddress) {
        This->m_SeqFile = seq_file_create(SequencePathAddress);
        if (seq_open((int) This)) {
            if (This->m_AutoPlay) {
                This->vtable->seq_play(This);
            }
        } else if (!This->m_OpenState) {
            This->m_OpenState = 1;
        }
    }
}

void bgm_set_sound(bgm_t *This, s32 SoundPathAddress) {
    if (This->m_Playing) {
        This->vtable->seq_stop(This);
    }

    if (This->m_Sound) {
        This->m_Sound->vtable->Destroy(This->m_Sound);
        This->m_Sound = NULL;
    }

    if (SoundPathAddress) {
        This->m_Sound = sound_create(SoundPathAddress);
        if (seq_open(This)) {
            if (This->m_AutoPlay) {
                This->vtable->seq_play(This);
            }
        } else if (!This->m_OpenState) {
            This->m_OpenState = 1;
        }
    }
}

bgm_vtable_t *bgm_get_vtable(void) {
    return &g_BGM_VTABLE;
}

s32 bgm_is_active(void) {
    return g_BgmActive;
}

extern u8 D_8008DF38[];

u8 *bgm_get_sequence_work(void) {
    return D_8008DF38;
}
