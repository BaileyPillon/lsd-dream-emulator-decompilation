#include "common.h"

#include "dream/dream_session_path.h"

/* Cursor state for dream_session_path_advance: current step and the half-table
   count captured on the first (SkipFirstHalf == 0) call. */
s32 g_DreamPathStep = 0;
s32 g_DreamPathHalfCount = 0;

const char *get_path_table(s32 *Count);
s32 file_driver_lookup_path(s32 arg0, s32 arg1);

s32 dream_session_path_advance(s32 SkipFirstHalf) {
    s32 count;
    s32 path_table;
    s32 previous_step;
    s32 step;
    s32 result;

    path_table = (s32) get_path_table(&count);
    previous_step = g_DreamPathStep;
    step = previous_step + 1;
    g_DreamPathStep = step;
    switch (step) {
        case 1:
            if (SkipFirstHalf != 0) {
                g_DreamPathStep = previous_step + 2;
            } else {
                count = count / 2;
                g_DreamPathHalfCount = count;
            }
            break;
        case 2:
            count -= g_DreamPathHalfCount;
            break;
        default:
            count = 0;
            break;
    }
    do {
        result = file_driver_lookup_path(path_table, count);
    } while (result == 0);
    return result;
}
