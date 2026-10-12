/* Unaccepted twelve-byte midpoint candidate for func_8001DDF4.
 * Prepare a private complete translation unit with prepare_overlap_candidate.py.
 * The complete image differs by 170 bytes; this is excluded from game coverage. */
extern s32 func_8001E110(func_8001E2E8_pt_t *, func_8001E2E8_box_t *,
                       func_8001E2E8_pt_t *, func_8001E2E8_pt_t *);
extern s32 func_8001F8B8(s32, s32 *, void *, s32 *, func_8001E2E8_pt_t *, func_8001E2E8_pt_t *);
extern s32 D_8008A838;

s32 func_8001DDF4(transform_t *This, s32 *out, void *contact, u8 *input) {
    func_8001E2E8_pt_t points[2];
    s32 best;
    s32 distance;
    func_8001E2E8_pt_t *mid;
    func_8001E2E8_pt_t *end;
    func_8001E2E8_pt_t *a;
    func_8001E2E8_pt_t *b;
    func_8001E2E8_pt_t *next;
    func_8001E2E8_box_t *box;
    s32 count;
    s32 paths;
    s32 i;
    s32 j;
    s32 k;
    s32 result;
    u32 bit;

    best = 0x7FFFFFFF;
    a = (func_8001E2E8_pt_t *)(input + 4);
    b = (func_8001E2E8_pt_t *)(input + 0x10);
    mid = points;
    end = points + 2;
    for (; mid < end; mid++, a = (func_8001E2E8_pt_t *)((u8 *)a + 0x18),
         b = (func_8001E2E8_pt_t *)((u8 *)b + 0x18)) {
        mid->x = (a->x + b->x) >> 1;
        mid->y = (a->y + b->y) >> 1;
        mid->z = (a->z + b->z) >> 1;
    }
    i = 0;
    This->m_Unk10 = 0;
    count = class_FA50_is_active(This->m_Unk7);
    j = 0;
    bit = 1;
    for (; i < count; i++) {
        box = (func_8001E2E8_box_t *)get_source_vertices(This->m_Unk7, i);
        if (func_8001E110(NULL, box, points, points + 1) != 0 &&
            func_8001F8B8(This->m_Unk7, &best, contact, &distance, points, points + 1) != 0 &&
            (D_8008A838 == 0 || distance > 0x200)) {
            This->m_Unk10 |= bit << i;
        }
    }
    if (This->m_Unk10 != 0) {
        result = 1;
        *out = 1;
        if (j != 0) {
            result = 2;
        }
    } else {
        *out = 0;
        paths = *(s32 *)input;
        for (i = 0; i < count; i++) {
            k = 0;
            a = (func_8001E2E8_pt_t *)(input + 4);
            box = (func_8001E2E8_box_t *)get_source_vertices(This->m_Unk7, i);
            for (; k < paths; k++) {
                j = 0;
                do {
                    if ((u32)(j++ - 1) < 2U) {
                        next = (func_8001E2E8_pt_t *)((u8 *)a + 0x18);
                        if (func_8001E110(NULL, box, a, next) != 0 &&
                            func_8001F8B8(This->m_Unk7, &best, contact, &distance, a, next) != 0 &&
                            distance > 0x200) {
                            This->m_Unk10 |= bit << i;
                            *out |= bit << k;
                        }
                    }
                    a++;
                } while (j < 4);
                a = (func_8001E2E8_pt_t *)((u8 *)a + 0x18);
            }
        }
        result = *out != 0;
    }
    return result;
}
