/* Analysis-only caller. The legacy branch preserves the prior local declaration
 * to record its diagnostics; neither caller is part of the game build. */
#include "common.h"

#ifdef LSD_COLLISION_LEGACY_DECLARATION
extern s32 func_8001F8B8(void *arg0, void *arg1, void *arg2, s32 arg3, void *arg4, void *arg5);
#else
#include "file/tmd_prim.h"
#endif

typedef struct collision_api_request {
    void *model;
    const vec3d_16_t *start;
    const vec3d_16_t *end;
    vec3d_16_t *hit;
    s32 *nearest;
    s32 *height;
} collision_api_request_t;

#include "abi_checks.h"

s32 collision_api_invoke(const collision_api_request_t *request) {
    return func_8001F8B8(request->model, request->nearest, request->hit,
                         request->height, request->start, request->end);
}
