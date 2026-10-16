/* Analysis-only call through the original actor virtual-table layout. */
#include "scene/actor.h"

void actor_children_set_flag(actor_t *actor, s32 flag) {
    actor->vtable->Unk23(actor, flag);
}
