/* Unaccepted padding-free reconstruction of func_8001DDF4.
 * The complete executable differs in 26 stack-offset bytes.
 * Control flow adapted from brian-oblivion/lsddecomp (CC0), commit
 * 90a398e4f429b4371be05648605fc198b9efb395,
 * src/graphics/scene_node.c: SceneNode__RaycastHullAgainstFaces.
 * This project's consumed count/bounds lookup views are retained.
 * See docs/OVERLAP_CONTROL_FLOW.md for attribution and evidence. */
extern s32 class_FA50_is_active(s32);
extern s32 D_8008A838;
extern s32 func_8001E110(func_8001E2E8_pt_t *,func_8001E2E8_box_t *,func_8001E2E8_pt_t *,func_8001E2E8_pt_t *);
typedef struct { s32 count; func_8001E2E8_pt_t v[8]; } collision_box_hull_t;
#define collision_source_bounds(m,i) collision_read_source_bounds((m),(i))
#define collision_query_faces(m,b,h,t,p,q) func_8001F8B8((void *)(m),(b),(vec3d_16_t *)(h),(t),(const vec3d_16_t *)(p),(const vec3d_16_t *)(q))
typedef struct {
    s32 value;
} collision_source_count_reference_t;

typedef char checked_collision_source_count_reference_t[
    (sizeof(collision_source_count_reference_t) == 4) ? 1 : -1];

static inline s32 collision_read_source_count(s32 model) {
    collision_source_count_reference_t reference = { class_FA50_is_active(model) };
    return reference.value;
}

typedef struct {
    func_8001E2E8_box_t *value;
} collision_source_bounds_reference_t;

typedef char checked_collision_source_bounds_reference_t[
    (sizeof(collision_source_bounds_reference_t) == 4) ? 1 : -1];

static inline func_8001E2E8_box_t *collision_read_source_bounds(s32 model, s32 index) {
    collision_source_bounds_reference_t reference = {
        (func_8001E2E8_box_t *) get_source_vertices(model, index)
    };
    return reference.value;
}

s32 func_8001DDF4(transform_t *self, s32 *hullHits, void *hitPoint, u8 *input) {
    collision_box_hull_t *hull = (collision_box_hull_t *)input;
    func_8001E2E8_pt_t center[2];
    func_8001E2E8_pt_t *c;
    func_8001E2E8_pt_t *opposite;
    s32 boundsCount;
    s32 i;
    func_8001E2E8_box_t *bounds;
    s32 hit;
    s32 hullCount;
    func_8001E2E8_pt_t *corner;
    s32 k;
    s32 j;
    s32 nearest;
    s32 height;

    nearest = 0x7FFFFFFF;

    corner = hull->v;
    opposite = hull->v + 2; /* the diagonally opposite corner of the same face */
    for (c = center; c < &center[2]; c++) {
        c->x = (corner->x + opposite->x) >> 1;
        c->y = (corner->y + opposite->y) >> 1;
        c->z = (corner->z + opposite->z) >> 1;
        corner += 4;
        opposite += 4;
    }

    self->m_Unk10 = 0;
    boundsCount = collision_read_source_count(self->m_Unk7);
    hit = 0;
    for (i = 0; i < boundsCount; i++) {
        bounds = collision_source_bounds(self->m_Unk7, i);
        if (func_8001E110(NULL, bounds, &center[0], &center[1])) {
            if (collision_query_faces(self->m_Unk7, &nearest, hitPoint, &height, &center[0], &center[1])) {
                if (D_8008A838 == 0) {
                    self->m_Unk10 |= 1 << i;
                } else if (height > 0x200) {
                    self->m_Unk10 |= 1 << i;
                }
            }
        }
    }

    if (self->m_Unk10 != 0) {
        *hullHits = 1;
        if (hit != 0) {
            return 2;
        }
        return 1;
    }

    *hullHits = 0;
    hullCount = hull->count;
    for (i = 0; i < boundsCount; i++) {
        bounds = collision_source_bounds(self->m_Unk7, i);
        corner = hull->v;
        for (k = 0; k < hullCount; k++) {
            for (j = 0; j < 4; j++) {
                if (j == 1 || j == 2) {
                    if (func_8001E110(NULL, bounds, corner, corner + 4)) {
                        if (collision_query_faces(self->m_Unk7, &nearest, hitPoint, &height, corner,
                                                   corner + 4)) {
                            if (height > 0x200) {
                                self->m_Unk10 |= 1 << i;
                                *hullHits |= 1 << k;
                            }
                        }
                    }
                }
                corner++;
            }
            corner += 4;
        }
    }

    return (*hullHits != 0);
}

#undef collision_source_bounds
#undef collision_query_faces
