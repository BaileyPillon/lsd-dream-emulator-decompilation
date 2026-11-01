#include "dream/dream_session.h"
#include "base/base.h"
#include "base/timer.h"
#include "dream/dream_session_path.h"
#include "dream/dream_sys.h"
#include "file/tim_image.h"
#include "file/tmd_model.h"
#include "scene/map_scene.h"
#include "scene/scene.h"
#include "sound/bgm.h"
#include "utils/cd_paths.h"

/* One dream's scene, rendering children and audio/model helpers. Construction
 * and destruction order are observable through notifications; preserve them. */
dream_session_vtable_t g_DREAM_SESSION_VTABLE = {
    0x1F230,
    base_class_destructor,
    dream_session_construct,
    dream_session_cleanup,
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
    dream_session_on_tick,
    NULL,
    dream_session_reset,
    dream_session_execute,
    dream_session_stop,
    dream_session_start,
    dream_session_update_actor,
    dream_session_tick,
    scene_noop,
    (void (*)(void *, void **, void *)) scene_update,
    (void (*)(void *, s32)) scene_finish,
    (void (*)(void *)) timer_begin_frame,
    (void (*)(void *)) timer_end_frame,
    (void (*)(void *, s32)) scene_set_duration,
    (void (*)(void *, s32)) scene_play_note,
    NULL,
    NULL,
    dream_session_noop,
    dream_session_noop2,
    dream_session_on_link_code,
};

s32 D_80086650[3] = { 0, -1200, 0 };
s32 D_8008665C[3] = { 0, -1200, 10000 };

dream_session_t *dream_session_create(game_graphics_ctx_t *GraphicsCtx, dream_sys_t *DreamSys, s32 FrameSyncMode) {
    dream_session_t *allocated = ALLOCATE_STRUCT(dream_session_t);

    if (allocated) {
        dream_session_get_vtable()->dream_session_construct(allocated, GraphicsCtx, DreamSys, FrameSyncMode);
        return allocated;
    }

    return NULL;
}

void dream_session_construct(dream_session_t *This,
                             game_graphics_ctx_t *GraphicsCtx,
                             dream_sys_t *DreamSys,
                             s32 FrameSyncMode) {
    void *tmdArgs[4];

    scene_get_vtable()->Construct(This, get_se_path(0), 0);
    This->vtable = dream_session_get_vtable();

    link_init_stage_objects();
    This->m_TextureHelper = tim_image_create("ETC\\ETC.TIM");
    This->m_TextureHelper->vtable->Unk14(This->m_TextureHelper);
    This->m_TextureHelper->vtable->Unk7(This->m_TextureHelper);

    tmdArgs[0] = NULL;
    tmdArgs[1] = "ETC\\DREAMER.TMD";

    This->m_Model = tmd_create(tmdArgs);
    This->m_Bgm = bgm_create(get_random_sound_type(NULL), 0, 1);

    dream_session_path_advance(1);
    frame_setup(FrameSyncMode == 0, 1, 1);

    This->m_GraphicsCtx = GraphicsCtx;
    GraphicsCtx->cls_3da54 = scene_renderer_create();
    GraphicsCtx->cls_32c00 = frame_phase_create();
    GraphicsCtx->cls_3acc8 = render_context_create(0, 1);

    This->m_DreamSys = DreamSys;
    This->vtable->Attach(This, DreamSys);
    DreamSys->vtable->dream_sys_set_actor(DreamSys, This->m_StageArg);
    DreamSys->vtable->dream_sys_set_texture(DreamSys, This->m_TextureHelper);
    This->vtable->dream_session_reset(This);
}

void link_destroy_models(void);

void dream_session_cleanup(dream_session_t *This) {
    game_graphics_ctx_t *graphics;
    bgm_t *bgm;
    tmd_model_t *model;

    graphics = This->m_GraphicsCtx;
    This->vtable->Detach(This, This->m_DreamSys);
    graphics->cls_3acc8 = graphics->cls_3acc8->vtable->Destroy(graphics->cls_3acc8);
    graphics->cls_32c00 = graphics->cls_32c00->vtable->Destroy(graphics->cls_32c00);
    graphics->cls_3da54 = graphics->cls_3da54->vtable->Destroy(graphics->cls_3da54);
    bgm = (bgm_t *) This->m_Bgm;
    bgm->vtable->Destroy(bgm);
    model = (tmd_model_t *) This->m_Model;
    model->vtable->Destroy(model);
    This->m_TextureHelper->vtable->Destruct(This->m_TextureHelper);
    link_destroy_models();
    scene_get_vtable()->Cleanup(This);
}

void dream_session_on_tick(dream_session_t *This, void **Sender, s32 Code) {
    s32 sender_type;

    /* Sender is a native object prefix. Route by its vtable's type word;
     * these masked IDs do not establish a complete concrete sender type. */

    scene_get_vtable()->OnNotify(This, Sender, Code);
    sender_type = *(s32 *) *Sender;

    if ((sender_type & 0xFFFF) == 0x1F34) {
        This->vtable->dream_session_noop2(This, Sender, Code);
    } else if ((sender_type & 0xFFFFF) == 0x2F230) {
        This->vtable->dream_session_on_link_code(This, (s32) Sender, Code);
    }
}

void dream_session_reset(dream_session_t *This) {
    This->m_State = 0;
}

void dream_session_execute(dream_session_t *This) {
    dream_sys_t *dream_sys = This->m_DreamSys;
    dream_sys->vtable->Attach(dream_sys, This->m_GraphicsCtx->cls_16634);
    dream_sys->vtable->Attach(dream_sys, This->m_GraphicsCtx->cls_32c00);
    dream_sys->vtable->dream_sys_set_transform(dream_sys, This->m_GraphicsCtx->cls_3da54);
    scene_get_vtable()->scene_run(This, This->m_GraphicsCtx, 0);
}

void dream_session_stop(dream_session_t *This) {
    dream_sys_t *dream_sys;

    dream_sys = This->m_DreamSys;
    scene_get_vtable()->Unk17(This);
    dream_sys->vtable->dream_sys_set_transform(dream_sys, 0);
    dream_sys->vtable->Detach(dream_sys, This->m_GraphicsCtx->cls_16634);
    dream_sys->vtable->Detach(dream_sys, This->m_Unk3);
}

typedef struct dream_session_child dream_session_child_t;
typedef struct dream_session_child_vtable dream_session_child_vtable_t;
typedef struct dream_session_actor_vtable dream_session_actor_vtable_t;

struct dream_session_child {
    dream_session_child_vtable_t *vtable;
};

struct dream_session_child_vtable {
    u32 pad[0x18];
    void (*Unk23)(dream_session_child_t *, s32);
};

struct dream_session_actor {
    dream_session_actor_vtable_t *vtable;
};

struct dream_session_actor_vtable {
    u32 pad0[0x11];
    void (*Unk16)(dream_session_actor_t *, void *);
    u32 pad1;
    void (*Unk18)(dream_session_actor_t *, s32);
    u32 pad2[8];
    void (*Unk27)(dream_session_actor_t *, dream_sys_t *, s32 *, s32 *, s32);
    void (*Unk28)(dream_session_actor_t *);
    u32 pad3[5];
    void (*Unk34)(dream_session_actor_t *);
    void (*Unk35)(dream_session_actor_t *);
    u32 pad4[6];
    dream_session_child_t *(*Unk42)(dream_session_actor_t *);
};

void dream_session_start(dream_session_t *This) {
    display_t *display;
    dream_session_actor_t *actor;
    dream_session_child_t *child;
    void *screen;

    display = This->m_GraphicsCtx->display;
    actor = This->m_Actor;
    screen = display->vtable->display_get_screen_size(display, 0);
    actor->vtable->Unk16(actor, screen);
    child = actor->vtable->Unk42(actor);
    child->vtable->Unk23(child, 1);
    actor->vtable->Unk18(actor, 0x4B0);
    actor->vtable->Unk27(actor, This->m_DreamSys, &D_80086650, &D_8008665C, 0);
    actor->vtable->Unk34(actor);
    This->m_State = 1;
}

void dream_session_update_actor(dream_session_t *This) {
    dream_session_actor_t *actor;

    actor = This->m_Actor;
    actor->vtable->Unk35(actor);
    actor->vtable->Unk28(actor);
}

void dream_session_tick(dream_session_t *This, void *Sender, s32 Code) {
    s32 state;
    s32 result;
    map_scene_t *map_scene;

    scene_get_vtable()->Unk20(This, Sender, Code);
    if (Code != 2) {
        return;
    }
    state = This->m_State;
    if (state == Code) {
        return;
    }
    if (state < 3) {
        if (state == 1) {
            goto state1;
        }
        return;
    }
    if (state == 3) {
        goto state3;
    }
    return;
state1:
    result = This->m_DreamSys->vtable->dream_sys_start_day(This->m_DreamSys);
    if (result >= 0) {
        open_map(This, result);
        return;
    }
    This->m_DreamSys->vtable->dream_sys_end_day(This->m_DreamSys, 0);
    This->m_Result = Code;
    This->vtable->scene_finish(This, 3);
    return;
state3:
    map_scene = (map_scene_t *) This->m_MapScene;
    ((void (*)(map_scene_t *)) map_scene->vtable->Unk17)(map_scene);
    map_scene = (map_scene_t *) This->m_MapScene;
    map_scene->vtable->Destroy(map_scene);
    open_map(This, This->m_DreamSys->vtable->dream_sys_get_current_map(This->m_DreamSys));
}

void open_map(dream_session_t *This, s32 MapIndex) {
    void **map_scene;

    This->m_MapScene =
        (s32) map_scene_create(This->m_StageArg, This->m_Bgm, (s32) This->m_TextureHelper, This->m_Model, MapIndex);
    This->vtable->Attach(This, This->m_MapScene);
    map_scene = (void **) This->m_MapScene;
    (*(void (**)(void **, void *, void *))(*(u32 *) map_scene + 0x44))(
        map_scene, This->m_GraphicsCtx, This->m_DreamSys);
    This->m_State = 2;
}

void dream_session_noop(dream_session_t *This) {
}

void dream_session_noop2(dream_session_t *This, void **Sender, s32 Code) {
}

void dream_session_on_link_code(dream_session_t *This, s32 SenderAddress, s32 Code) {
    s32 end_day_mode;
    s32 day_result;
    s16 cinematic[4];
    dream_sys_t *dream_sys;
    dream_sys_vtable_t *vtable;

    switch (Code) {
        case 4:
            (*(void (**)(s32, s32))(*(s32 *) This->m_MapScene + 0x48))(This->m_MapScene, SenderAddress);
            (*(void (**)(s32))(*(s32 *) This->m_MapScene + 4))(This->m_MapScene);
            if (This->m_DreamSys->vtable->dream_sys_end_day(This->m_DreamSys, 0) == 0) {
                This->m_DreamSys->vtable->dream_sys_get_cinematic(cinematic, This->m_DreamSys);
                day_result = 2;
                if (cinematic[1] < 0) {
                    day_result = 1;
                }
                This->m_Result = day_result;
                goto block_4_join;
            }
            This->m_Result = 3;
        block_4_join:
            This->vtable->scene_finish(This, 3);
            break;
        case 5:
        case 6:
        case 7:
        case 8:
        case 10:
            This->m_State = 3;
            break;
        case 12:
        case 13:
            (*(void (**)(s32, s32))(*(s32 *) This->m_MapScene + 0x48))(This->m_MapScene, SenderAddress);
            (*(void (**)(s32))(*(s32 *) This->m_MapScene + 4))(This->m_MapScene);
            dream_sys = This->m_DreamSys;
            vtable = dream_sys->vtable;
            end_day_mode = 1;
            if (Code != 12) {
                end_day_mode = 2;
            }
            vtable->dream_sys_end_day(dream_sys, end_day_mode);
            This->m_Result = 3;
            This->vtable->scene_finish(This, 3);
            break;
    }
}

dream_session_vtable_t *dream_session_get_vtable(void) {
    return &g_DREAM_SESSION_VTABLE;
}
