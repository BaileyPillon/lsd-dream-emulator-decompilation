/* Unaccepted source hypothesis. Insert this helper and function at the
 * generation dispatcher's INCLUDE_ASM in src/dream/dream_generation.c.
 * The consumed method-word return reserves the original 40-byte frame,
 * but its remaining stack store is absent from the original. No padding. */
typedef struct {
    void (*method)(void *, s32 *);
} generation_structure_update_t;

static inline generation_structure_update_t generation_structure_get_update(generation_structure_t *obj) {
    generation_structure_update_t update;
    update.method = obj->vtable->Update;
    return update;
}

void dream_generation_update_structure_entities(s32 *position) {
    s32 i;
    generation_structure_t **cursor;

    if (g_GenerationType >= 0) {
        if (g_GenerationStructureCount > 0) {
            cursor = g_GenerationStructures;
            i = 0;
            do {
                generation_structure_t *obj = *cursor;
                generation_structure_update_t update = generation_structure_get_update(obj);
                update.method(obj, position);
                cursor++;
                i++;
            } while (i < g_GenerationStructureCount);
        }
    }
}
