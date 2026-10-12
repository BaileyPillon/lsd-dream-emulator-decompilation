/* Unaccepted live-argument source hypothesis. Replace the generation-update
 * INCLUDE_ASM with this fragment in a private complete translation unit. */
typedef struct { base_class_t *object; s32 *position; } structure_update_t;
static inline void structure_update(structure_update_t *value) {
    ((void (*)(base_class_t *, s32 *))(*(u32 *)((u8 *)value->object->vtable + 0xEC)))(value->object, value->position);
}
void dream_generation_update_structure_entities(s32 *position) {
    s32 i;
    base_class_t **cursor;


    if (g_GenerationType >= 0) {
        if (g_GenerationStructureCount > 0) {
            cursor = g_GenerationStructures;
            i = 0;
            do {
                base_class_t *obj = *cursor;
                structure_update_t value;

                value.object = obj; value.position = position;
                structure_update(&value);
                cursor++;
                i++;
            } while (i < g_GenerationStructureCount);
        }
    }
}
