#include "scene/render_context.h"
#include "base/transform.h"
#include "graphics/light.h"
#include "file/cd_stream.h"
#include "file/file_object.h"
#include "scene/notify_node.h"

cd_stream_t *func_80048894(void);
notify_node_t *func_8004D38C(void);
file_object_t *class_1C92C_create(u32);
extern vec3d_t D_8008682C;

extern render_context_vtable_t D_800866E8;

extern s8 D_800868FC[];
extern s32 D_8008688C[];
extern s32 D_800868A8[];
extern s32 D_80086974[];
extern s32 D_800869CC[];
extern s32 D_80086904[];
extern s32 D_80086990[3];
extern s32 D_8008699C[3];
extern s32 D_800869A8[3];
extern s32 D_800869B4[3];
extern s32 D_800869C0[3];
extern s32 D_8008A980;

extern vec3d_t D_80086838[];
s32 func_8004B930(render_context_t *, s32, s32);
s32 func_8004BA40(render_context_t *, s32 *, s32, s32, s32, s32, s32);

s32 func_8004BCE0(render_context_t *This);
void func_8004D0D0(render_context_t *This, s32 *Unk);
void func_8004D140(render_context_t *This, void (*arg1)(s32, s32), void (*arg2)(s32, s32));

typedef struct {
    u8 m_Pad[0x74];
    void (*Unk29)(void *);
    u8 m_Pad2[4];
    void (*Unk30)(void *);
    u8 m_Pad3[4];
    void (*Unk33)(void *);
} render_context_slot_obj_vtable_t;

typedef struct render_context_slot_obj {
    render_context_slot_obj_vtable_t *vtable;
    u8 m_Pad[0x2C];
    s16 m_Unk30_1;
} render_context_slot_obj_t;

typedef struct {
    void *m_Pad;
    s32 (*Destroy)(void *);
} render_context_slot_child_vtable_t;

typedef struct render_context_slot_child {
    render_context_slot_child_vtable_t *vtable;
} render_context_slot_child_t;

typedef struct {
    u8 m_Pad[0x2C];
    render_context_slot_child_t *m_Child;
} render_context_slot_link_t;

typedef struct render_context_slot_item {
    void *m_Unk0;
    u8 m_Pad[0xC];
    u32 m_Flags;
    s32 m_Unk5;
    s32 m_Unk6;
    s32 m_Unk7;
    s32 m_Unk8;
} render_context_slot_item_t;

typedef struct {
    s16 m_Flag;
    s16 m_Pad;
    render_context_slot_obj_t *m_Obj;
    render_context_slot_link_t *m_Link;
    u8 m_UnkC[4];
    render_context_slot_item_t **m_Items;
    u8 m_Rest[8];
} render_context_slot_t;

void *get_display(void);

render_context_t *render_context_create(u32 Unk1, u32 Unk2) {
    render_context_t *allocated = ALLOCATE_STRUCT(render_context_t);

    if (allocated) {
        func_8004D244()->Construct(allocated, Unk1, Unk2);
        return allocated;
    }

    return NULL;
}

typedef struct {
    u16 m_Flag;
    s16 m_Index;
    cd_stream_t *m_Stream;
    file_object_t *m_File;
    notify_node_t *m_Node;
    notify_node_t **m_Items;
    s32 m_Unk14;
    s32 m_Unk18;
} render_context_construct_slot_t;

/* Construct seven stream slots and their notification grid. */
void func_8004A534(render_context_t *This, vec3d_t *origin, s32 arg2) {
    vec3d_t pos;
    s32 index;
    render_context_construct_slot_t *slot;
    cd_stream_t *object;
    cd_stream_t *created;
    notify_node_t *node;
    notify_node_t **cursor;
    notify_node_t **end;
    u32 flags;
    s32 initial_x;

    func_800428E4()->Construct(This);
    This->vtable = func_8004D244();
    if (origin != NULL) {
        *(vec3d_t *) &This->m_Unk20 = *origin;
    } else {
        *(vec3d_t *) &This->m_Unk20 = D_8008682C;
    }
    index = 0;
    initial_x = 0x400;
    This->m_Unk107 = 0;
    *(u16 *) &This->m_Unk108 = 0;
    This->m_Unk109 = 0;
    This->m_Unk27 = 0;
    This->m_Unk26 = 0;
    This->m_Unk57 = 0;
    This->m_Unk119 = 0;
    do {
        slot = (render_context_construct_slot_t *) ((u8 *) This + 0xEC + index * 0x1C);
        created = func_80048894();
        slot->m_Stream = created;
        *(u16 *) &created->m_Unk7 = created->m_Unk3 != 0;
        slot->m_Stream->m_Unk11_2 = index;
        object = slot->m_Stream;
        ((void (*)(void *, s32)) object->vtable->Unk33)(object, arg2);
        slot->m_Unk14 = 0;
        slot->m_Unk18 = 0;
        slot->m_Index = index;
        slot->m_Flag = 0;
        slot->m_File = class_1C92C_create(0);
        node = func_8004D38C();
        slot->m_Node = node;
        ((void (*)(void *, void *, void *)) node->vtable->Unk18)(node, This, &This->m_Unk20);
        slot->m_Items = memory_allocate_mem(0x668);
        if (slot->m_Items == NULL) {
            return;
        }
        pos.x = initial_x;
        pos.y = 0;
        pos.z = initial_x;
        end = (notify_node_t **) ((u8 *) slot->m_Items + 0x668);
        for (cursor = slot->m_Items; cursor < end; cursor++) {
            node = func_8004D38C();
            *cursor = node;
            ((void (*)(void *, void *, void *)) node->vtable->Unk18)(node, slot->m_Node, &pos);
            pos.x += 0x800;
            if (pos.x > 0xA400) {
                pos.x = initial_x;
                pos.z += 0x800;
            }
            node = *cursor;
            ((void (*)(void *, s32)) node->vtable->Unk27)(node, 1);
            node = *cursor;
            flags = node->m_Unk3;
            node->m_Unk3 = flags | 0x80000000;
        }
        index++;
    } while (index < 7);
    This->vtable->Attach((base_class_t *) This, (base_class_t *) get_display());
    This->vtable->Unk15(This);
}

void func_8004A7C0(render_context_t *This) {
    render_context_slot_t *slot;
    render_context_slot_item_t **start;
    render_context_slot_item_t **end;
    render_context_slot_item_t **cursor;
    render_context_slot_item_t *entry;
    render_context_slot_link_t *link;
    render_context_slot_child_t *child;
    base_class_t *obj;
    s32 index;
    s32 offset;

    This->vtable->Detach((base_class_t *) This, (base_class_t *) get_display());
    index = 0;
    offset = 0xEC;
    do {
        slot = (render_context_slot_t *) ((u8 *) This + offset);
        This->vtable->Unk33(This, 6, slot, index);
        obj = (base_class_t *) slot->m_Obj;
        if (obj != NULL) {
            obj->vtable->Destroy(obj);
        }
        link = slot->m_Link;
        if (link != NULL) {
            child = link->m_Child;
            if (child != NULL) {
                child->vtable->Destroy(child);
            }
            slot->m_Link = (render_context_slot_link_t *) ((base_class_t *) slot->m_Link)
                               ->vtable->Destroy((base_class_t *) slot->m_Link);
        }
        obj = *(base_class_t **) slot->m_UnkC;
        if (obj != NULL) {
            obj->vtable->Destroy(obj);
        }
        start = slot->m_Items;
        end = (render_context_slot_item_t **) ((u8 *) start + 0x668);
        cursor = start;
        while (cursor < end) {
            entry = *cursor;
            if (entry != NULL) {
                ((base_class_t *) entry)->vtable->Destroy((base_class_t *) entry);
            }
            cursor++;
        }
        memory_free_mem(slot->m_Items);
        offset += 0x1C;
        index++;
    } while (index < 7);
    func_800428E4()->Cleanup(This);
}

void func_8004A984(render_context_t *This, s32 **Unk2, s32 Unk3) {
    func_8001E57C()->OnNotify(This, Unk2, Unk3);

    if ((**Unk2 & 0xF) == 1) {
        This->vtable->Unk63(This, Unk2, Unk3);
    }
}

void func_8004AA10(render_context_t *This) {
    This->m_Unk25 = 0;
    This->m_Unk57 = 0;
    This->m_Unk33 = 0;
    This->vtable->Unk54(This, D_8008A980);
    This->m_Unk114 = -1;
    This->m_Unk115 = -1;
    This->m_Unk116 = -1;
    This->m_Unk117 = -1;
}

void func_8004AA6C(render_context_t *This, s32 arg1, void *arg2) {
    void *obj;

    ((void (*)(void *, s32)) func_8001E57C()->Unk33)(This, arg1);
    switch (arg1) {
        case 6:
            obj = *(void **) ((u8 *) arg2 + 0x14);
            if (obj != NULL) {
                *(void **) ((u8 *) arg2 + 0x14) = (*(void *(**) (void *) )(*(s32 *) obj + 4))(obj);
            }
            /* fallthrough */
        case 7:
            This->m_Unk110 = (s32) arg2;
            ((void (*)(void *, s32)) This->vtable->Notify)(This, arg1);
            break;
    }
}

void func_8004AB24(render_context_t *This) {
    if (This->m_Unk27) {
        This->vtable->Unk60(This);
        This->vtable->Unk78(This);
    }
}

void func_8004AB88(render_context_t *This, u8 **Unk) {
    if (**Unk == 52) {
        This->vtable->Unk51(This);
    }
}

void func_8004ABD0(render_context_t *This) {
    s32 index;
    s32 offset;
    render_context_slot_t *slot;
    render_context_slot_link_t *link;
    render_context_slot_child_t *child;

    index = 0;
    offset = 0xEC;
    do {
        slot = (render_context_slot_t *) ((u8 *) This + offset);
        slot->m_Obj->vtable->Unk29(slot->m_Obj);
        slot->m_Flag = 0;
        This->vtable->Unk65(This, slot);
        link = slot->m_Link;
        child = link->m_Child;
        if (child != 0) {
            link->m_Child = (render_context_slot_child_t *) child->vtable->Destroy(child);
        }
        offset += 0x1C;
        This->vtable->Unk33(This, 6, slot, index);
        slot->m_Obj->vtable->Unk33(slot->m_Obj);
        index += 1;
    } while (index < 7);
    This->m_Unk109 = 0;
    *(s16 *) &This->m_Unk108 = 0;
    This->vtable->Unk79(This);
}

typedef struct acf8_obj_vtable {
    /* 0x00 */ u8 pad[0x44];
    /* 0x44 */ void (*Unk16)(void *, s32, void *);
    /* 0x48 */ void (*Unk17)(void *, s32, void *);
} acf8_obj_vtable_t;

typedef struct acf8_obj {
    /* 0x00 */ acf8_obj_vtable_t *vtable;
} acf8_obj_t;

void func_8004ACF8(render_context_t *This, s32 count, void *arg2, void *arg3) {
    s32 i;
    acf8_obj_t *obj;

    for (i = 0; i < count; i++) {
        obj = This->vtable->Unk45(This, i);
        obj->vtable->Unk16(obj, 1, arg3);
        arg3 = (u8 *) arg3 + 3;
        obj->vtable->Unk17(obj, 1, arg2);
        arg2 = (u8 *) arg2 + 6;
    }
}

void func_8004ADC4(render_context_t *This, s32 Unk2, s32 Unk3) {
    This->m_Unk23 = Unk2;
    This->m_Unk24 = Unk3;
}

void func_8004ADD0(render_context_t *This, s32 Value) {
    This->m_Unk57 = Value;
}

void func_8004ADD8(render_context_t *This, s32 **arg1, s32 arg2) {
    char dummy_stack_padding[24];
    s32 *p;

    if (&dummy_stack_padding[0] == &dummy_stack_padding[23]) {
    }

    switch (arg2) {
        case 2:
        case 3:
        case 5:
        case 6:
        case 7:
        case 8:
            p = This->m_Unk57;
            if (p != NULL && *p != 0) {
                do {
                    if (*p == **arg1) {
                        This->vtable->Unk74(This, arg1, arg2);
                    }
                    p++;
                } while (*p != 0);
            }
            break;
    }
}

typedef struct aea4_arg {
    /* 0x00 */ s32 pad0[3];
    /* 0x0C */ s32 unk_c;
    /* 0x10 */ s32 pad1;
    /* 0x14 */ s32 unk_14;
} aea4_arg_t;

typedef struct {
    s32 w[12];
} blk30_t;

void func_8004AFE0(render_context_t *This, s32 *Unk1, s32 Unk2);
void func_8004B030(render_context_t *This, s8 *arg1, s32 arg2);
void func_8004B100(render_context_t *This, aea4_arg_t *arg1, s32 arg2);

void func_8004AEA4(render_context_t *This, aea4_arg_t *arg1, s32 arg2) {
    blk30_t saved;
    func_8004C1C0_out_t out;
    s32 extra;
    s32 keep;
    s32 *gate;

    if (arg1->unk_c != 0) {
        extra = arg1->unk_14 + 0x38;
    } else {
        extra = 0;
    }
    if (This->vtable->Unk67(This, &out, (func_8004C1C0_pos_t *) extra) != 0) {
        return;
    }
    keep = This->m_Unk33;
    saved = *(blk30_t *) &This->m_Unk34;
    gate = (s32 *) This->m_Unk25;
    if (gate[1] == 0) {
        func_8004AFE0(This, (s32 *) &out, 3);
    } else {
        func_8004B030(This, (s8 *) &out, 3);
    }
    func_8004B100(This, arg1, arg2);
    This->m_Unk33 = keep;
    *(blk30_t *) &This->m_Unk34 = saved;
}

void func_8004AFE0(render_context_t *This, s32 *Unk1, s32 Unk2) {
    s8 v3;

    This->m_Unk30_1 = *((s8 *) Unk1 + 2) - 1;
    v3 = *((s8 *) Unk1 + 3);
    This->m_Unk31 = Unk2;
    This->m_Unk32 = Unk2;
    This->m_Unk30_2 = v3 - 1;
    func_8004C93C(This);
}

void func_8004B030(render_context_t *This, s8 *arg1, s32 arg2) {
    s32 b2;
    s32 b3;
    s32 orig2;
    s32 orig3;
    s32 adj2;
    s32 adj3;

    b2 = arg1[2];
    b3 = arg1[3];
    orig2 = b2;
    orig3 = b3;
    adj2 = arg2;
    adj3 = adj2;
    if (b2 == 0) {
        adj2 = adj3 - 1;
    } else {
        b2--;
    }
    if (orig2 == 0x13) {
        adj2--;
    }
    if (orig3 == 0) {
        adj3--;
    } else {
        b3--;
    }
    if (orig3 == 0x13) {
        adj3--;
    }
    This->m_Unk33 = 1;
    This->m_Unk34 = This->vtable->Unk72(This, *(s32 *) (arg1 + 0x28));
    This->m_Unk35_1 = b2;
    This->m_Unk35_2 = b3;
    This->m_Unk36_1 = adj2;
    This->m_Unk36_2 = adj3;
}

void func_8004B100(render_context_t *This, aea4_arg_t *arg1, s32 arg2) {
    u8 *rec;
    u8 *sl;
    u8 *grid;
    u8 *q;
    s32 i;
    s32 j;
    s32 k;

    rec = (u8 *) This + 0x8C;
    for (i = 0; i < This->m_Unk33; i++) {
        sl = (u8 *) This + (*(s32 *) rec * 0x1C + 0xEC);
        if (*(s16 *) (*(u8 **) (sl + 4) + 0x2C) != 0) {
            grid = *(u8 **) (sl + 0x10) + *(s16 *) (rec + 4) * 4 + *(s16 *) (rec + 6) * 0x50;
            for (j = 0; j < *(s16 *) (rec + 0xA); j++) {
                for (k = 0; k < *(s16 *) (rec + 8); k++) {
                    *(u16 *) ((u8 *) This + 0x1C0) = *(u16 *) ((u8 *) This + 0xBC);
                    *(u8 *) ((u8 *) This + 0x1C2) = (u8) (*(u8 *) (rec + 4) + k);
                    *(u8 *) ((u8 *) This + 0x1C3) = (u8) (*(u8 *) (rec + 6) + j);
                    func_8004B2D4(*(void **) grid, arg1, arg2);
                    q = *(u8 **) (*(u8 **) grid + 0x38);
                    while (q != 0) {
                        func_8004B2D4(q, arg1, arg2);
                        q = *(u8 **) (q + 0x38);
                    }
                    grid += 4;
                }
                grid += (0x14 - *(s16 *) (rec + 8)) * 4;
            }
        }
        rec += 0xC;
    }
}

void func_8004B2D4(render_context_t *This, aea4_arg_t *arg1, s32 arg2) {
    if (This && (This->m_Unk12_2 & 0x80) != 0) {
        ((void (*)(render_context_t *)) This->vtable->OnNotify)(This);
    }
}

s32 *func_8004B31C(render_context_t *This) {
    return &This->m_Unk111;
}

void func_8004B324(void) {
}

void func_8004B32C(render_context_t *This, s32 Value) {
    This->m_Unk28 = Value;
    This->m_Unk29_2 = Value >> 11;
    This->m_Unk29_1 = Value >> 12;
}

void func_8004B344(render_context_t *This, s32 Unk) {
    This->vtable->Unk15(This);
    This->m_Unk25 = Unk;
}

s32 func_8004B44C(void *, void *, s32, void *, void *);

typedef struct {
    u8 m_data[8];
    s16 m_hi;
} func_8004B38C_pkt_t;

s32 func_8004B38C(render_context_t *This, void *arg1, s32 arg2, void *arg3) {
    s8 sp18[0x10];

    This->m_Unk26 = arg2;
    *(func_8004B38C_pkt_t *) &This->m_Unk46 = *(func_8004B38C_pkt_t *) arg3;
    return ((s32(*)(void *, s32, void *, void *)) This->vtable->Unk61)(
        This, func_8004B44C(arg1, sp18, This->m_Unk25, &This->m_Unk20, arg3), sp18, D_80086904);
}

void func_8004B418(render_context_t *This, s32 Unk2, s32 Unk3) {
    s8 unk[16];

    func_8004B44C(Unk2, unk, This->m_Unk25, &This->m_Unk20, Unk3);
}

typedef struct {
    /* 0x0 */ s16 m_Width;
    /* 0x2 */ s16 m_Height;
    /* 0x4 */ s32 m_Mode;
} func_8004B44C_grid_t;

typedef struct {
    /* 0x0 */ s8 m_Unk0;
    /* 0x1 */ s8 m_Unk1;
    /* 0x2 */ s8 m_Unk2;
    /* 0x3 */ s8 m_Unk3;
    /* 0x4 */ s16 m_Unk4;
    /* 0x6 */ s16 m_Unk6;
    /* 0x8 */ s16 m_Unk8;
} func_8004B44C_info_t;

static inline s32 render_context_world_axis(s32 cell, s32 base, s32 local) {
    s32 position = (cell << 11) + base;
    s32 adjusted = local + 0x400;

    return position + adjusted;
}

/* Compute a streamed grid cell's origin and the position within that cell. */
s32 func_8004B44C(void *arg0, void *arg1, s32 arg2, void *arg3, void *arg4) {
    s32 index;
    s32 height;
    s32 row;
    s32 origin_x;
    s32 origin_z;
    s32 y;
    s32 base_x;

    if (((func_8004B44C_grid_t *)arg2)->m_Mode == 0) {
        row = ((func_8004B44C_info_t *)arg4)->m_Unk1;
        height = ((func_8004B44C_grid_t *)arg2)->m_Height;
        index = ((func_8004B44C_info_t *)arg4)->m_Unk0 +
             (((func_8004B44C_grid_t *)arg2)->m_Width * row);
    } else {
        height = 1;
        row = 0;
        index = 0;
    }
    origin_x = (((vec3d_t *)arg3)->x - (((func_8004B44C_grid_t *)arg2)->m_Width * 0x5000)) +
          (((func_8004B44C_info_t *)arg4)->m_Unk0 * 0xA000);
    origin_z = ((vec3d_t *)arg3)->z - (height * 0x5000);
    ((vec3d_t *)arg1)->x = origin_x;
    if (row & 1) {
        ((vec3d_t *)arg1)->x = origin_x - 0x5000;
    }
    y = ((vec3d_t *)arg3)->y;
    base_x = ((vec3d_t *)arg1)->x;
    ((vec3d_t *)arg1)->z = origin_z + (row * 0xA000);
    ((vec3d_t *)arg1)->y = y;
    ((vec3d_t *)arg0)->x = render_context_world_axis(((func_8004B44C_info_t *)arg4)->m_Unk2, base_x, ((func_8004B44C_info_t *)arg4)->m_Unk4);
    ((vec3d_t *)arg0)->y = ((func_8004B44C_info_t *)arg4)->m_Unk6 + ((vec3d_t *)arg1)->y;
    ((vec3d_t *)arg0)->z = render_context_world_axis(((func_8004B44C_info_t *)arg4)->m_Unk3, ((vec3d_t *)arg1)->z, ((func_8004B44C_info_t *)arg4)->m_Unk8);
    ((vec3d_t *)arg1)->x += 0x5000;
    ((vec3d_t *)arg1)->z += 0x5000;
    return index;
}

void func_8004B570(render_context_t *This) {
    This->m_Unk27 = 1;
}

void func_8004B57C(render_context_t *This) {
    This->vtable->Unk47(This);
    This->m_Unk27 = 0;
}


s32 func_8004B5BC(render_context_t *This) {
    func_8004C1C0_out_t buf;
    u16 old;
    void *inner;
    s32 index;
    s32 kind;

    if (This->vtable->Unk66(This, &buf, 0) == 0) {
        return 0;
    }
    inner = *(void **) ((u8 *) buf.obj + 4);
    index = *(s16 *) ((u8 *) inner + 0x32);
    kind = D_800868FC[index];
    if (*(s32 *) (This->m_Unk25 + 4) == 0) {
        This->vtable->Unk61(This, buf.divisor, &buf.vx, D_80086974[kind]);
    }
    This->vtable->Unk73(This);
    old = *(u16 *) &This->m_Unk46;
    *(func_8004C1C0_out_t *) &This->m_Unk46 = buf;
    if ((s16) old != buf.labels.pair) {
        This->vtable->Notify(This, 5);
    }
    return kind;
}

typedef struct {
    u16 m_Flag;
    u16 m_Index;
    cd_stream_t *m_Stream;
    void *m_File;
    notify_node_t *m_Node;
    notify_node_t **m_Items;
    s32 m_Unk14;
    s32 m_Unk18;
} render_context_grid_slot_t;
typedef struct {
    s32 m_Flag;
    u8 m_Pad[0x14];
    vec3d_t m_Pos;
} render_context_grid_coords_t;
/* Position active stream slots and submit their grid rows. */
void func_8004B700(render_context_t *This, s32 index, vec3d_t *origin, u8 *selected) {
    s32 rows[7][3];
    s32 mask;
    s32 width;
    render_context_grid_coords_t *coords;
    s32 parity;
    s32 i;
    s32 row_offset;
    s32 count;
    vec3d_t *delta;
    s32 *row;
    render_context_grid_slot_t *slot;
    if (selected != NULL) {
        width = *(s16 *) This->m_Unk25;
        count = 0;
        i = 0;
        row_offset = 0;
        parity = (index / width) & 1;
        mask = func_8004B930(This, index, parity);
        do {
            slot = This->vtable->Unk69(This, i);
            slot->m_Index = selected[0];
            if (selected[1] != 0) {
                delta = &D_80086838[selected[0]];
                coords = (render_context_grid_coords_t *) slot->m_Node->m_Unk4;
                if (*(s32 *) (This->m_Unk25 + 4) == 0) {
                    coords->m_Pos.x = origin->x + delta->x;
                    coords->m_Pos.y = origin->y;
                    coords->m_Pos.z = origin->z + delta->z;
                } else {
                    coords->m_Pos.x = origin->x - 0x5000;
                    coords->m_Pos.y = origin->y + delta->y;
                    coords->m_Pos.z = origin->z - 0x5000;
                }
                row = (s32 *) ((u8 *) rows + row_offset);
                ((render_context_grid_coords_t *) slot->m_Node->m_Unk4)->m_Flag = 0;
                func_8004BA40(This, row, width, parity, index, mask, selected[0]);
                row_offset += 0xC;
                count++;
            }
            i++;
            selected += 2;
        } while (i < 7);
        i = 0;
        do {
            slot = (render_context_grid_slot_t *) ((u8 *) This + 0xEC + i * 0x1C);
            i++;
            slot->m_Stream->m_Unk11_2 = slot->m_Index;
        } while (i < 7);
        ((void (*)(render_context_t *, void *, s32)) This->vtable->Unk62)(This, rows, count);
    }
}

/* Build the horizontal or vertical grid boundary mask. */
s32 func_8004B930(render_context_t *This, s32 index, s32 parity) {
    s32 width = *(s16 *)(This->m_Unk25 + 0);
    s32 mode = *(s32 *)(This->m_Unk25 + 4);
    s32 height = *(s16 *)(This->m_Unk25 + 2);
    s32 result;

    if (mode == 0) {
        result = 0;
        if (index < width) result |= 3;
        if (index >= width * (height - 1)) result |= 0x60;
        if (index % width == 0) {
            if (parity != 0) result |= 0x25; else result |= 4;
        }
        if ((index + 1) % width == 0) {
            if (parity != 0) result |= 0x10; else result |= 0x52;
        }
    } else {
        s32 i;

        result = -1;
        for (i = 0; i < height; i++) {
            result <<= 1;
        }
    }
    return ~result;
}

/* Write the permitted neighbor's linear index before querying its stage path. */
static inline void render_context_write_grid_index(render_context_t *This, s32 *out,
                                                   s32 columns, s32 parity, s32 index,
                                                   s32 direction) {
    s32 stride;
    s32 offset;
    s32 *table;

    if (*(s32 *)(This->m_Unk25 + 4) != 0) {
        ((volatile s32 *)out)[1] = index + direction;
        return;
    }
    {
        table = &D_800868A8[direction * 3];
        stride = table[0];
        if (stride == 0) {
            stride = table[1];
            ((volatile s32 *)out)[1] = index + stride;
            return;
        } else {
            offset = columns * stride;
            if (parity != 0) {
                offset += table[1];
            } else {
                offset += table[2];
            }
            ((volatile s32 *)out)[1] = index + offset;
            return;
        }
    }
}

typedef const char *(*render_context_stage_path_fn)(void *, s32, s32, s32);

/* Output words contain the path address, linear index and direction. */
s32 func_8004BA40(render_context_t *This, s32 *out, s32 columns, s32 parity,
                  s32 index, s32 mask, s32 direction) {
    if (mask & D_8008688C[direction]) {
        render_context_write_grid_index(This, out, columns, parity, index, direction);
        out[0] = (s32)((render_context_stage_path_fn)This->m_Unk23)(
            (void *)This->m_Unk24, out[1], 0, 0);
        out[2] = direction;
        return 1;
    } else {
        out[0] = 0;
    }
    out[2] = direction;
    return 0;
}


typedef struct func_8004BB3C_inner func_8004BB3C_inner_t;

typedef struct func_8004BB3C_inner_vtable {
    /* 0x00 */ u8 pad[0x74];
    /* 0x74 */ void (*Unk28)(func_8004BB3C_inner_t *);
    /* 0x78 */ void (*Unk29)(func_8004BB3C_inner_t *, s32);
} func_8004BB3C_inner_vtable_t;

struct func_8004BB3C_inner {
    /* 0x00 */ func_8004BB3C_inner_vtable_t *vtable;
    /* 0x04 */ u8 pad[0x26];
    /* 0x2A */ u16 field_2a;
    /* 0x2C */ s16 field_2c;
    /* 0x2E */ u16 pad_2e;
    /* 0x30 */ u16 field_30;
};

typedef struct func_8004BB3C_slot {
    /* 0x00 */ s16 flag;
    /* 0x02 */ s16 pad;
    /* 0x04 */ func_8004BB3C_inner_t *obj;
} func_8004BB3C_slot_t;

typedef struct func_8004BB3C_ent {
    /* 0x00 */ s32 id;
    /* 0x04 */ u16 half;
    /* 0x06 */ u16 pad;
    /* 0x08 */ s32 arg;
} func_8004BB3C_ent_t;

void func_8004BB3C(render_context_t *This, func_8004BB3C_ent_t *ents, s32 count) {
    s32 i;
    s32 one;
    func_8004BB3C_slot_t *slot;
    func_8004BB3C_inner_t *obj;

    for (i = 0; i < count; i += 1) {
        one = 1;
        slot = This->vtable->Unk69(This, ents->arg);
        This->vtable->Unk33(This, 6, slot, i);
        if (ents->id != 0) {
            if (slot->obj->field_2c != 0) {
                This->vtable->Unk65(This, slot);
            }
            slot->obj->field_30 = ents->half;
            slot->obj->vtable->Unk29(slot->obj, ents->id);
            slot->flag = one;
            This->m_Unk107 = one;
        } else {
            if (slot->obj->field_2c != 0) {
                This->vtable->Unk65(This, slot);
            }
            obj = slot->obj;
            if (obj->field_2a != 0) {
                obj->vtable->Unk28(obj);
                slot->flag = 0;
            }
        }
        ents += 1;
    }
    *(s16 *) &This->m_Unk108 = func_8004BCE0(This);
}

s32 func_8004BCE0(render_context_t *This) {
    s32 count = 0;
    s32 i = 0;

loop:
    if (This->m_Unk58_1 != 0) {
        count++;
    }
    This = (render_context_t *) ((char *) This + 0x1C);
    i++;
    if (i < 7) {
        goto loop;
    }

    return count;
}

typedef struct {
    u8 m_Pad[0x2A];
    u16 m_Unk2A;
    s16 m_Unk2C;
    s16 m_Unk2E;
} render_context_stream_state_t;

typedef struct {
    u16 m_Flag;
    u16 m_Pad;
    render_context_stream_state_t *m_Obj;
} render_context_update_slot_t;

void func_8004BD14(render_context_t *This, s32 unused, s32 arg2) {
    s32 i;
    s32 state;
    u16 count;
    render_context_update_slot_t *slot;

    if (arg2 == 2) {
        i = 0;
        do {
            slot = (render_context_update_slot_t *) ((u8 *) This + 0xEC + i * 0x1C);
            if (slot->m_Obj->m_Unk2E != 0) {
                slot->m_Obj->m_Unk2E = 0;
                This->vtable->Unk33(This, 7, slot, i);
            }
            state = This->m_Unk107;
            if (state == 1 && slot->m_Flag != 0) {
                if (slot->m_Obj->m_Unk2C != 0) {
                    This->vtable->Unk64(This, slot);
                    slot->m_Obj->m_Unk2C = 2;
                    slot->m_Flag = 0;
                    count = *(u16 *) &This->m_Unk108 - 1;
                    *(u16 *) &This->m_Unk108 = count;
                    if (count == 0) {
                        *(u16 *) &This->m_Unk108 = 0;
                        This->m_Unk107 = 0;
                        This->m_Unk109 = state;
                    }
                } else if (slot->m_Obj->m_Unk2A == 0) {
                    slot->m_Flag = 0;
                }
            }
            i++;
        } while (i < 7);
    }
}

#include "scene/render_context.h"
#include "file/cd_stream.h"
#include "file/file_object.h"
#include "file/tmd_model.h"
#include "file/tmd_prim.h"
#include "scene/notify_node.h"
#include "psx/libgs.h"
typedef struct {
    u8 m_Pad[0xC];
    vec3d_t m_Position;
    u16 m_Unk18;
    u16 m_Heading;
    u8 m_Pad1[0x10];
    u16 m_Unk2C;
    u16 m_Type;
    s32 m_Special;
    s32 m_Next;
    s32 m_Model;
    s32 m_Unk3C;
} render_link_payload_t;
typedef struct {
    s32 m_Flag;
    u8 m_Pad[0x14];
    vec3d_t m_Position;
    u8 m_Pad1[0x20];
    u16 *m_Angles;
} render_link_coords_t;
typedef struct {
    u16 m_Flag;
    s16 m_Index;
    cd_stream_t *m_Stream;
    file_object_t *m_File;
    notify_node_t *m_Node;
    notify_node_t **m_Items;
    s32 m_Unk14;
    s32 m_Unk18;
} render_link_slot_t;
static inline tmd_model_t *render_link_model(cd_stream_t *stream) {
    tmd_model_arg_t args;
    s32 header = stream->m_Unk3;
    args.m_Unk0 = header + *(s32 *)(header + 4) + *(s32 *)(header + 8);
    return tmd_create(&args);
}
void func_8004BE54(render_context_t *unused, render_link_slot_t *slot) {
    render_link_payload_t payload;
    cd_stream_t *model;
    file_object_t *object;
    s32 header;
    tmd_model_t *child;
    tmd_prim_t *part;
    notify_node_t **data;
    s32 extra;
    s32 index;
    s32 offset;
    s32 extra_offset;
    notify_node_t **entry;
    notify_node_t *item;
    render_link_coords_t *coords;
    u16 *angles;
    u32 mask;
    u32 flags;
    model = slot->m_Stream;
    object = slot->m_File;
    header = model->m_Unk3;
    child = (tmd_model_t *)object->m_Unk10;
    /* Capture the grid before clearing the file size, as the native reader does. */
    header += *(s32 *)(header + 4);
    object->m_Unk4 = 0;
    object->m_Unk3 = header;
    if (child != NULL) {
        child->vtable->Destroy((base_class_t *)child);
    }
    object->m_Unk10=(s32)render_link_model(model);
    index = 0;
    mask = 0x80000000;
    offset = 0;
    extra_offset = 0x640; /* Additional nodes follow the 400 fixed grid cells. */
    payload.m_Next = 0;
    while (1) {
        part=(tmd_prim_t *)object->vtable->class_1C92C_unk29(object,(u8 *)&payload,index);
        if (part == NULL) {
            break;
        }
        if (part == (tmd_prim_t *)-1) {
            entry = (notify_node_t **)((u8 *)slot->m_Items + offset);
            flags = (*entry)->m_Unk3;
            (*entry)->m_Unk3 = flags | mask;
            (*entry)->m_Unk7 = 0;
            (*entry)->m_Unk5 = 0;
        } else {
            extra=payload.m_Special;
            data=slot->m_Items;
            if(extra){entry=(notify_node_t **)((u8 *)data+extra_offset);extra_offset+=4;}
            else entry=(notify_node_t **)((u8 *)data+offset);
            (*entry)->m_Unk7 = (s32)part;
            {
                notify_node_t *bound = *entry;
                bound->m_Unk5 = (s32)((tmd_prim_t *)bound->m_Unk7)->m_Unk3;
            }
            item = *entry;
            GsLinkObject4(((tmd_prim_t *)item->m_Unk7)->m_Unk3, (u8 *)item + 0x10, 0);
            coords = (render_link_coords_t *)(*entry)->m_Unk4;
            coords->m_Position = payload.m_Position;
            angles=((render_link_coords_t *)(*entry)->m_Unk4)->m_Angles;
            angles[8]=0;angles[9]=payload.m_Heading;angles[10]=0;
            (*entry)->m_Unk12_2 = payload.m_Type;
            ((render_link_coords_t *)(*entry)->m_Unk4)->m_Flag = 0;
            flags = (*entry)->m_Unk3;
            (*entry)->m_Unk3 = flags | mask;
        }
        if (payload.m_Next != 0) {
            (*entry)->m_Unk13 = (s32)*(notify_node_t **)(extra_offset+(s32)slot->m_Items);
        } else {
            offset += 4;
            index++;
            (*entry)->m_Unk13 = 0;
        }
    }
}

void func_8004C0AC(render_context_t *This, render_context_slot_t *slot) {
    render_context_slot_obj_t *obj;
    render_context_slot_item_t **start;
    render_context_slot_item_t **end;
    render_context_slot_item_t **cursor;

    obj = slot->m_Obj;
    if (obj->m_Unk30_1 >= 0) {
        obj->vtable->Unk30(obj);
        start = slot->m_Items;
        end = (render_context_slot_item_t **) ((u8 *) start + 0x668);
        cursor = start;
        while (cursor < end) {
            (*cursor)->m_Flags |= 0x80000000;
            (*cursor)->m_Unk8 = 0;
            (*cursor)->m_Unk6 = 0;
            cursor++;
        }
    }
}

/* Return the cached record on success; optionally expose the current
 * position pointer even when no output record is requested. */
func_8004C1C0_out_t *func_8004C158(render_context_t *This,
                               func_8004C1C0_out_t *out,
                               func_8004C1C0_pos_t **position_out) {
    func_8004C1C0_pos_t *position;
    func_8004C1C0_out_t *result;

    position = (func_8004C1C0_pos_t *) (*(s32 *) (This->m_Unk26 + 0x14) + 0x18);
    if (position_out != NULL) {
        *position_out = position;
    }
    if ((out == NULL) || (This->vtable->Unk67(This, out, position) == 0)) {
        result = (func_8004C1C0_out_t *) ((u8 *) This + 0xBC);
    } else {
        result = NULL;
    }
    return result;
}

s16 func_8004C368(render_context_t *, s8 *, s32);


/* Resolve world coordinates into the active stream slot and local grid cell. */
s32 func_8004C1C0(render_context_t *This, func_8004C1C0_out_t *out, func_8004C1C0_pos_t *pos) {
    void *obj;
    s32 *coordB;
    s32 *coordA;
    s16 val;
    u16 x;
    u16 z;

    obj = This->vtable->Unk70(This, pos);
    if (obj != NULL) {
        val = *(s16 *) ((u8 *) (*(s32 **) ((u8 *) obj + 4)) + 0x30);
        out->divisor = val;
        func_8004C368(This, (s8 *) out, val);
        coordA = *(s32 **) ((u8 *) (*(s32 **) ((u8 *) This->vtable->Unk69(
                     This, *(s16 *) ((u8 *) (*(s32 **) ((u8 *) obj + 4)) + 0x32)) + 0xC)) + 0x14);
        out->vx = coordA[0x18 / 4] + 0x5000;
        out->vy = coordA[0x1C / 4];
        out->vz = coordA[0x20 / 4] + 0x5000;
        coordB = *(s32 **) ((u8 *) (*(s32 **) ((u8 *) obj + 0xC)) + 0x14);
        out->rx = pos->x - out->vx;
        out->ry = pos->y;
        out->rz = pos->z - out->vz;
        out->dx = (pos->x - coordB[0x18 / 4]) / 2048;
        out->dz = (pos->z - coordB[0x20 / 4]) / 2048;
        x = pos->x - 0x400;
        out->x = x - ((u16) coordB[0x18 / 4] + (out->dx * 2048));
        out->y = (u16) pos->y;
        z = pos->z - 0x400;
        out->z = z - ((u16) coordB[0x20 / 4] + (out->dz * 2048));
        out->obj = obj;
        return 0;
    }
    return 1;
}

s16 func_8004C368(render_context_t *This, s8 *out, s32 val) {
    s16 d;

    d = *(s16 *) This->m_Unk25;
    *out = val % d;
    d = *(s16 *) This->m_Unk25;
    out[1] = val / d;
    return d;
}

s32 func_8004C3F0(render_context_t *This, s8 *Unk) {
    func_8004C368(This, Unk, *(s16 *) (*(s32 *) (This->m_Unk110 + 4) + 48));
    return This->m_Unk110;
}

s32 func_8004C434(render_context_t *This, int Unk) {
    s32 i = 0;
    s32 offset = 0xEC;
    char *ptr;
    s32 result;

    do {
        ptr = (char *) This + offset;

        if (*(s16 *) (*(s32 *) (ptr + 4) + 0x32) == Unk) {
            result = (s32) ptr;
            goto exit;
        }

        i++;
        result = i < 7;
        offset += 0x1C;
    } while (result);

exit:
    return result;
}

typedef struct {
    /* 0x00 */ s32 field0;
    /* 0x04 */ s32 field4;
    /* 0x08 */ s32 field8;
} func_8004C470_probe_t;

void *func_8004C470(render_context_t *This, func_8004C470_probe_t *arg1) {
    void *result;
    u8 *inner;
    s32 *coords;
    s32 i = 0;
    s32 range = 0xA000;
    s32 offset = 0;
    s32 c6;
    s32 c8;

    for (; i < 7; i += 1, offset -= 0x800) {
        result = This->vtable->Unk69(This, i);
        inner = *(u8 **) ((u8 *) result + 0xC);
        coords = *(s32 **) ((inner + 0x14));
        if ((c6 = coords[6], arg1->field0 >= c6) && arg1->field0 < c6 + range && arg1->field8 >= coords[8] &&
            arg1->field8 < (c8 = coords[8]) + range) {
            if (*(s32 *) (This->m_Unk25 + 4) == 0) {
                return result;
            }
            if (offset >= arg1->field4 && offset - 0x800 < arg1->field4) {
                return result;
            }
        }
    }
    return NULL;
}
s32 func_8004C588(render_context_t *This, s32 Unk) {
    s32 ret = 0;
    s32 i = 0;
    s32 offset = 0xEC;

    do {
        u8 *ptr = *(u8 **) ((u8 *) This + offset + 4);

        if (*(s16 *) (ptr + 0x32) == Unk) {
            ret = i;
            break;
        }

        i++;
        offset += 0x1C;
    } while (i < 7);

    return ret;
}

s32 func_8004C5D0(render_context_t *This, s32 Unk) {
    s32 i;
    s32 offset;
    char *ptr;

    i = 0;
    offset = 0xEC;
    do {
        ptr = *(char **) ((u8 *) This + offset + 4);
        if (*(s16 *) (ptr + 0x30) == Unk) {
            if (*(s16 *) (ptr + 0x2C) != 0) {
                return i;
            }
        }
        i++;
        offset += 0x1C;
    } while (i < 7);

    return -1;
}

void func_8004C6A8(render_context_t *, s32, s32);
void func_8004CC74(render_context_t *);
void func_8004CE24(render_context_t *, s32);

void func_8004C620(render_context_t *This) {
    s32 doubled;

    if (This->m_Unk109 != 0) {
        doubled = This->m_Unk29_1 * 2;
        func_8004CE24(This, 0);
        if (*(s32 *) (This->m_Unk25 + 4) == 0) {
            func_8004C6A8(This, doubled, This->m_Unk29_2);
        } else {
            func_8004CC74(This);
        }
        func_8004CE24(This, 1);
    }
}

INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004C6A8);

typedef struct {
    s32 index;
    s16 x;
    s16 y;
    s16 width;
    s16 height;
} render_context_line_t;

s32 func_8004CAF0(render_context_t *, render_context_line_t *, s32, s32, s32, s32, s32, s32);

void func_8004C93C(render_context_t *This) {
    s32 x;
    s32 y;
    s32 z;
    s32 w;
    s32 mode;
    s32 flag;
    s32 total;
    s32 wrapped;
    s32 count;
    s32 clamped;
    u8 *rec;

    flag = 0;
    x = This->m_Unk30_1;
    z = This->m_Unk31;
    w = This->m_Unk32;
    mode = 3;
    if (x < 0) {
        x += 0x14;
        flag = 1;
        mode = 2;
    }
    y = This->m_Unk30_2;
    rec = (u8 *) This + 0x8C;
    if (y < 0) {
        y += 0x14;
        if (flag != 0) {
            x -= 0xA;
            mode = 0;
        } else {
            mode = 0;
            if (x < 0xA) {
                x += 0xA;
            } else {
                x -= 0xA;
                mode = 1;
            }
            rec = (u8 *) This + 0x8C;
        }
    }
    This->m_Unk34 = This->vtable->Unk71(This, mode);
    clamped = x;
    if (x < 0) {
        clamped = 0;
    }
    total = x + z;
    This->m_Unk35_1 = clamped;
    This->m_Unk35_2 = y;
    if (total >= 0x15) {
        wrapped = total - 0x14;
        This->m_Unk36_1 = z - wrapped;
        count = func_8004CAF0(This, (render_context_line_t *) rec, 0, mode, x, y, z, w) + 1;
        rec = (u8 *) This + (count * 0xC + 0x8C);
        *(s32 *) rec = This->vtable->Unk71(This, mode + 1);
        *(s16 *) (rec + 4) = 0;
        *(u16 *) (rec + 6) = This->m_Unk35_2;
        *(s16 *) (rec + 8) = wrapped;
        *(u16 *) (rec + 0xA) = This->m_Unk36_2;
    } else {
        This->m_Unk36_1 = z;
        count = func_8004CAF0(This, (render_context_line_t *) rec, 0, mode, x, y, z, w);
    }
    count++;
    This->m_Unk33 = count;
}

static inline s16 render_context_line_remaining(s32 width, s32 next) {
    s32 remaining = width + 0x14;

    return remaining - next;
}

static inline void render_context_line_initialize(render_context_t *This,
                                                   render_context_line_t *line,
                                                   s32 mode, s32 x, s32 delta) {
    line->index = This->vtable->Unk71(This, mode);
    line->x = x + delta;
}

/* Split a wrapped row into the adjacent streamed grid cells. */
s32 func_8004CAF0(render_context_t *This, render_context_line_t *line, s32 count, s32 mode,
                 s32 x, s32 y, s32 width, s32 height) {
    s32 wrapped;
    s32 total;
    s32 next_mode;

    if (y + height >= 0x15) {
        wrapped = y + height - 0x14;
        line->height = height - wrapped;
        count += 1;
        line = (render_context_line_t *) ((u8 *) This + (count * 0xC + 0x8C));
        total = wrapped;
        if (x < 0xA) {
            next_mode = mode + 2;
            render_context_line_initialize(This, line, next_mode, x, 10);
            line->height = total;
        } else {
            next_mode = mode + 3;
            render_context_line_initialize(This, line, next_mode, x, -10);
            line->height = total;
        }
        total = line->x + width;
        line->y = 0;
        if (total >= 0x15) {
            count += 1;
            line->width = render_context_line_remaining(width, total);
            line = (render_context_line_t *) ((u8 *) This + (count * 0xC + 0x8C));
            line->index = This->vtable->Unk71(This, next_mode + 1);
            line->x = 0;
            line->y = 0;
            line->width = total - 0x14;
            line->height = wrapped;
        } else {
            line->width = width;
        }
    } else {
        line->height = height;
    }
    return count;
}

s32 func_8004CD38(const render_context_cell_bounds_t *bounds, const u8 *point);
s32 func_8004CDA4(render_context_t *This, s32 unused, s32 index, s32 arg3);

void func_8004CC74(render_context_t *This) {
    func_8004C1C0_out_t buf;
    s32 unused;
    s32 next;

    This->vtable->Unk66(This, &buf, 0);
    This->m_Unk33 = 0;
    next = func_8004CDA4(This, unused, 0, buf.divisor);
    This->m_Unk33 = next;
    if (func_8004CD38(This->m_NextSlotExclusionBounds, (const u8 *) &buf + 2) != 0) {
        next = buf.divisor + 1;
        if (next < ((s16 *) This->m_Unk25)[1]) {
            This->m_Unk33 = func_8004CDA4(This, unused, This->m_Unk33, next);
        }
    }
    next = buf.divisor - 1;
    if (next >= 0) {
        This->m_Unk33 = func_8004CDA4(This, unused, This->m_Unk33, next);
    }
}

INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004CD38);

/* The original reads signed X/Z cells against mixed-width inclusive bounds.
 * Null bounds returns outside, enabling consideration of the next stream
 * slot. Current C candidates reproduce bounded behavior but still differ
 * in register allocation; the original assembly remains authoritative. */

s32 func_8004CDA4(render_context_t *This, s32 unused, s32 index, s32 arg3) {
    s32 *dest;
    s32 off;

    off = (index * 12) + 0x8C;
    dest = (s32 *) ((u8 *) This + off);
    __builtin_memcpy(dest, D_80086990, 0xC);
    *dest = ((s32(*)(render_context_t *, s32)) This->vtable->Unk72)(This, arg3);
    return index + 1;
}

void func_8004CE24(render_context_t *This, s32 arg1) {
    u8 *rec;
    u8 *sl;
    u8 *grid;
    u8 *q;
    s32 i;
    s32 j;
    s32 k;

    rec = (u8 *) This + 0x8C;
    for (i = 0; i < This->m_Unk33; i++) {
        sl = (u8 *) This + (*(s32 *) rec * 0x1C + 0xEC);
        if (*(s16 *) (*(u8 **) (sl + 4) + 0x2C) != 0) {
            grid = *(u8 **) (sl + 0x10) + *(s16 *) (rec + 4) * 4 + *(s16 *) (rec + 6) * 0x50;
            for (j = 0; j < *(s16 *) (rec + 0xA); j++) {
                for (k = 0; k < *(s16 *) (rec + 8); k++) {
                    if (arg1 != 0) {
                        *(s32 *) (*(u8 **) grid + 0x10) &= 0x7FFFFFFF;
                    } else {
                        *(s32 *) (*(u8 **) grid + 0x10) |= 0x80000000;
                    }
                    q = *(u8 **) (*(u8 **) grid + 0x38);
                    while (q != 0) {
                        if (arg1 != 0) {
                            *(s32 *) (q + 0x10) &= 0x7FFFFFFF;
                        } else {
                            *(s32 *) (q + 0x10) |= 0x80000000;
                        }
                        q = *(u8 **) (q + 0x38);
                    }
                    grid += 4;
                }
                grid += (0x14 - *(s16 *) (rec + 8)) * 4;
            }
        }
        rec += 0xC;
    }
}

void *func_8004CFA8(render_context_t *This) {
    return &This->m_Unk114;
}

void func_8004CFB0(render_context_t *This, const render_context_cell_bounds_t *bounds) {
    This->m_NextSlotExclusionBounds = bounds;
}

typedef struct scale_row {
    s16 unk0;
    s16 unk1;
    s16 unk2;
    s16 scale;
} scale_row_t;

void func_8004CFB8(render_context_t *This, s32 arg1, s32 arg2) {
    scale_row_t *table;
    scale_row_t *row;
    s32 scale;
    s32 prod;

    if (arg1 > 0) {
        table = (scale_row_t *) D_8008699C;
        if (arg2 != 0) {
            This->m_Unk120 = (s32) D_800869A8;
            goto use;
        }
    } else {
        table = (scale_row_t *) D_800869B4;
        if (arg2 != 0) {
            table = (scale_row_t *) D_800869C0;
        }
    }
    This->m_Unk120 = (s32) table;
use:
    row = (scale_row_t *) This->m_Unk120;
    scale = row->scale;
    if (arg1 < 0) {
        prod = scale * (~arg1 + 1);
    } else {
        prod = scale * arg1;
    }
    This->m_Unk119 = prod;
}

void func_8004D028(render_context_t *This) {
    s32 temp_v0;

    if (This->m_Unk119 > 0) {
        func_8004D140(This, func_8004D0D0, 0);
        temp_v0 = This->m_Unk119 - 1;
        This->m_Unk119 = temp_v0;
        if (temp_v0 == 0) {
            This->m_Unk119 = -1;
        }
    }
}

void func_8004D088(render_context_t *This) {
    if (This->m_Unk119) {
        func_8004D140(This, func_8004D108, 0);
        This->m_Unk119 = 0;
    }
}

void func_8004D0D0(render_context_t *This, s32 *Unk) {
    (*(void (**)(s32 *, s32, s32))(*Unk + 72))(Unk, 0, This->m_Unk120);
}

// INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004D108);
void func_8004D108(render_context_t *This, s32 *Unk) {
    (*(void (**)(s32 *, s32, s32 *))(*Unk + 72))(Unk, 1, &D_800869CC);
}

void func_8004D1D0(render_context_t *This, void (*arg1)(render_context_t *, s32), void *arg2);

void func_8004D140(render_context_t *This, void (*arg1)(s32, s32), void (*arg2)(s32, s32)) {
    s32 i;
    s32 off;
    s32 ptr;

    i = 0;
    off = 0xEC;
    do {
        ptr = (s32) This + off;
        if (arg2 != NULL) {
            arg2((s32) This, ptr);
        }
        func_8004D1D0(This, arg1, (void *) ptr);
        i += 1;
        off += 0x1C;
    } while (i < 7);
}

void func_8004D1D0(render_context_t *This, void (*arg1)(render_context_t *, s32), void *arg2) {
    s32 *start;
    s32 *cursor;
    s32 *end;

    start = *(s32 **) ((u8 *) arg2 + 0x10);
    end = (s32 *) ((u8 *) start + 0x668);
    cursor = start;
    while (cursor < end) {
        arg1(This, *cursor++);
    }
}

render_context_vtable_t *func_8004D244(void) {
    return &D_800866E8;
}
