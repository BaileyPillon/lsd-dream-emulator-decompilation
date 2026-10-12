/* Unaccepted, padding-free source-layout candidate. Insert at this function's
 * INCLUDE_ASM in src/dream/dream_generation.c. Complete executable equality is required.
 * The caller supplies a three-word position vector; its lifetime stays external. */
void dream_generation_update_structure_entities(s32 *position) {
    s32 i;
    base_class_t **cursor;


    if (g_GenerationType >= 0) {
        if (g_GenerationStructureCount > 0) {
            cursor = g_GenerationStructures;
            i = 0;
            do {
                base_class_t *obj = *cursor;

                ((void (*)(base_class_t *, s32 *))(*(u32 *)((u8 *)obj->vtable + 0xEC)))(obj, position);
                cursor++;
                i++;
            } while (i < g_GenerationStructureCount);
        }
    }
}
