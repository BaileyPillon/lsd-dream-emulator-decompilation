/* Unaccepted source candidate for the 108-byte bounds predicate.
 * The complete executable still differs at 21 byte positions. This fragment
 * belongs outside the matching build until complete executable equality.
 * The surrounding unit supplies render_context_cell_bounds_t and common types.
 */
s32 func_8004CD38(s32 arg0, const u8 *arg1) {
    const render_context_cell_bounds_t *box = (const render_context_cell_bounds_t *) arg0;
    s32 outside = 1;
    s32 work;
    u32 shifted_x;
    u32 shifted_z;

    if (box != 0) {
        work = arg1[0];
        arg0 = box->min_x;
        shifted_x = ((u32) work) << 24;
        work = ((s32) shifted_x) >> 24;
        work = ((s32) work) < arg0;
        arg0 = ((s32) shifted_x) >> 24;
        if (work == 0) {
            work = box->max_x;
            work = ((s32) work) < arg0;
            if (work == 0) {
                work = arg1[1];
                arg0 = box->min_z;
                shifted_z = ((u32) work) << 24;
                work = ((s32) shifted_z) >> 24;
                work = ((s32) work) < arg0;
                if (work == 0) {
                    outside = (box->max_z) < (((s32) shifted_z) >> 24);
                }
            }
        }
    }
    return outside;
}
