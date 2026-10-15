/* Unaccepted source hypothesis for func_8004441C. The complete image still
 * differs by twelve bytes across four instructions; no padding or assembly.
 * See README.md and docs/UI_SCALE.md for the native zero-denominator boundary.
 */
static inline s16 ui_add_scale(s16 old, s32 ratio, s32 negative) {
    u16 added;
    s32 candidate = old + (s16)ratio;
    candidate = candidate < 30001;
    if (candidate == 0) {
        added = 1;
        if (negative == 0) added = 30000;
    } else {
        added = ratio + old;
    }
    return added;
}
void func_8004441C(ui_sprite_t *This, s32 arg1, u8 *arg2) {
    s32 neg_x;
    s32 neg_y;
    s32 ratio_x;
    s32 ratio_y;
    s32 num_x;
    s32 den_x;
    s32 num_y;
    s32 den_y;
    s32 result;
    u16 added;

    neg_x = 0;
    neg_y = 0;
    if (*(s16 *)arg2 < 0 || *(s16 *)(arg2 + 2) < 0) {
        neg_x = 1;
    }
    if (*(s16 *)(arg2 + 4) < 0 || *(s16 *)(arg2 + 6) < 0) {
        neg_y = 1;
    }

    den_x = *(s16 *)(arg2 + 2);
    if (den_x != 0) {
        num_x = *(s16 *)arg2;
        ratio_x = ((num_x / den_x) << 12) + (((num_x % den_x) << 12) / den_x);
    }
    den_y = *(s16 *)(arg2 + 6);
    if (den_y != 0) {
        num_y = *(s16 *)(arg2 + 4);
        ratio_y = ((num_y / den_y) << 12) + (((num_y % den_y) << 12) / den_y);
    }

    if (arg1 != 0) {
        if (*(s16 *)(arg2 + 2) == 0) {
            This->m_Unk23_0 = 0x1000;
        } else {
            result = (s16)ratio_x;
            if (result >= 30001) {
                result = 30000;
            }
            This->m_Unk23_0 = result;
        }
        if (*(s16 *)(arg2 + 6) == 0) {
            added = 0x1000;
            This->m_Unk23_1 = added;
        } else {
            result = (s16)ratio_y;
            if (result >= 30001) {
                result = 30000;
            }
            This->m_Unk23_1 = result;
        }
    } else {
        This->m_Unk23_0 = ui_add_scale(This->m_Unk23_0, ratio_x, neg_x);
        This->m_Unk23_1 = ui_add_scale(This->m_Unk23_1, ratio_y, neg_y);
    }
}
