/* Unaccepted, padding-free source-layout candidate. Insert at this function's
 * INCLUDE_ASM in src/dream/dream_generation.c. Complete executable equality is required.
 * The caller supplies a three-word position vector; its lifetime stays external. */
void dream_generation_update_structure_entities(s32 *position) {
    s32 i;
    generation_structure_t **cursor;


    if (g_GenerationType >= 0) {
        if (g_GenerationStructureCount > 0) {
            cursor = g_GenerationStructures;
            i = 0;
            do {
                generation_structure_t *obj = *cursor;

                obj->vtable->Update(obj, position);
                cursor++;
                i++;
            } while (i < g_GenerationStructureCount);
        }
    }
}
