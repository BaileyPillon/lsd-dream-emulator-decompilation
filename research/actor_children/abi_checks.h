#include "scene/actor.h"
#include "scene/scene_node.h"

typedef char actor_child_pointer_width[(sizeof(void *) == 4) ? 1 : -1];
typedef char actor_child_actor_size[(sizeof(actor_t) == 0x98) ? 1 : -1];
typedef char actor_child_node_size[(sizeof(scene_node_t) == 0x58) ? 1 : -1];
typedef char actor_child_table_size[(sizeof(actor_vtable_t) == 0x144) ? 1 : -1];
typedef char actor_child_count_offset[((u32)&((actor_t *)0)->m_Unk26 == 0x6C) ? 1 : -1];
typedef char actor_child_list_offset[((u32)&((actor_t *)0)->m_Unk27 == 0x70) ? 1 : -1];
typedef char actor_child_flags_offset[((u32)&((scene_node_t *)0)->m_Unk3 == 0x10) ? 1 : -1];
typedef char actor_child_method_offset[((u32)&((actor_vtable_t *)0)->Unk23 == 0x60) ? 1 : -1];
