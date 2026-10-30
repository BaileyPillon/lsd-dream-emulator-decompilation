#include "common.h"
#include "file/tmd_prim.h"

/* Global enumeration value read by collision loops. Reset writes one;
   the getter ignores its model argument. This is not an instance count.
   Address-only symbol, defined via undefined_syms_auto.txt. */
extern s32 D_8008AC4C;

void class_FA50_reset_flag(void) {
    D_8008AC4C = 1;
}

s32 class_FA50_is_active(s32 arg0) {
    return D_8008AC4C;
}

typedef vec3d_16_t vec3s_t;

typedef struct {
    vec3s_t min;
    vec3s_t max;
} bbox_t;

typedef struct {
    s16 *verts;
    s32 count;
} vtx_list_t;

typedef struct {
    s32 unk0;
    s16 v[24];
} cube_t;

/* Compute bounds from the model's eight-byte vertex records. */
void func_8001F3B0(s32 arg0, s16 *arg1) {
    s32 i = 0;
    s16 *min_y = arg1 + 1;
    s16 *min_z = arg1 + 2;
    s16 *max_x = arg1 + 3;
    s16 *max_y = arg1 + 4;
    s16 *max_z = arg1 + 5;
    vtx_list_t *list = *(vtx_list_t **)(arg0 + 0x10);
    s16 *src = list->verts;
    s32 n = list->count - 1;

    arg1[0] = src[0];
    arg1[1] = src[1];
    arg1[2] = src[2];
    ((vec3s_t *)arg1)[1] = ((vec3s_t *)arg1)[0];
    if (i < n) {
        do {
            src += 4;
            if (src[0] < arg1[0]) arg1[0] = src[0];
            if (src[1] < *min_y) *min_y = src[1];
            if (src[2] < *min_z) *min_z = src[2];
            if (*max_x < src[0]) *max_x = src[0];
            if (*max_y < src[1]) *max_y = src[1];
            if (*max_z < src[2]) *max_z = src[2];
            i++;
        } while (i < n);
    }
}

/* Shared bounds scratch storage. The refresher writes six signed halfwords
   (minimum and maximum); the accessor ignores caller model/index arguments. */
extern s16 D_8008B21C[];

/* Copies the model geometry's bounding box into the shared vertex buffer. */
void refresh_source_vertices(s32 arg0) {
    func_8001F3B0(arg0, D_8008B21C);
}

/* Return the shared bounds storage, independent of the caller's index. */
void *get_source_vertices(s32 unused_model, s32 unused_index) {
    return &D_8008B21C;
}

typedef struct {
    s32 one;
    s16 buf[6];
} tmp_t;

/* Expand the model bounds into the eight corners of a cuboid. */
void func_8001F51C(s32 arg0, cube_t *arg1) {
    tmp_t tmp;

    func_8001F3B0(arg0, tmp.buf);
    tmp.one = 1;
    arg1->v[0] = tmp.buf[0];
    arg1->v[1] = tmp.buf[1];
    arg1->v[2] = tmp.buf[2];
    arg1->v[3] = tmp.buf[0];
    arg1->v[4] = tmp.buf[4];
    arg1->v[5] = tmp.buf[2];
    arg1->v[6] = tmp.buf[3];
    arg1->v[7] = tmp.buf[4];
    arg1->v[8] = tmp.buf[2];
    arg1->v[9] = tmp.buf[3];
    arg1->v[10] = tmp.buf[1];
    arg1->v[11] = tmp.buf[2];
    arg1->v[12] = tmp.buf[0];
    arg1->v[13] = tmp.buf[1];
    arg1->v[14] = tmp.buf[5];
    arg1->v[15] = tmp.buf[0];
    arg1->v[16] = tmp.buf[4];
    arg1->v[17] = tmp.buf[5];
    arg1->v[18] = tmp.buf[3];
    arg1->v[19] = tmp.buf[4];
    arg1->v[20] = tmp.buf[5];
    arg1->v[21] = tmp.buf[3];
    arg1->v[22] = tmp.buf[1];
    arg1->v[23] = tmp.buf[5];
    arg1->unk0 = 1;
}

typedef struct {
    u16 vx, vy, vz;
} svec_t;

void func_8001F66C(s32 arg0, s32 arg1, s32 arg2, s32 arg3) {
    s32 i;
    svec_t buf[8];

    for (i = 0; i < *(s32 *) arg0; i++) {
        svec_t *p = (svec_t *) ((u8 *) arg0 + 4 + i * 0x30);

        if (arg1 != 0) {
            __builtin_memcpy(buf, p, 48);
            p[3] = buf[0];
            p[2] = buf[1];
            p[6] = buf[2];
            p[7] = buf[3];
            p[0] = buf[4];
            p[1] = buf[5];
            p[5] = buf[6];
            p[4] = buf[7];
            if (arg2 == 0) {
                s32 j;
                for (j = 0; j < 4; j++) {
                    p[j].vx = p[j].vx + arg3;
                }
            } else {
                s32 j;
                for (j = 0; j < 4; j++) {
                    p[4 + j].vx = p[4 + j].vx + arg3;
                }
            }
        } else if (arg2 == 0) {
            s32 j;
            for (j = 0; j < 4; j++) {
                p[j].vz = p[j].vz + arg3;
            }
        } else {
            s32 j;
            for (j = 0; j < 4; j++) {
                p[4 + j].vz = p[4 + j].vz + arg3;
            }
        }
    }
}

/* Adapted from brian-oblivion/lsddecomp (CC0),
 *90a398e4f429b4371be05648605fc198b9efb395, TmdModel__RaycastFaces.
 * The unused VECTOR and second distance slot reproduce the retail frame.
 * They are compiler-layout compatibility storage, not game behavior. */
typedef vec3s_t model_point_t;
typedef struct {s16 x,y,z,pad;} sdk_svector_t;
typedef struct {s32 x,y,z,pad;} sdk_vector_t;
typedef struct {model_point_t org,dir;} collision_ray_t;
typedef struct {model_point_t min,max;} collision_bounds_t;
typedef union {sdk_vector_t v;collision_bounds_t b;} collision_scratch_t;
enum {COLLISION_RAY_MISS=0,COLLISION_RAY_HIT=1,COLLISION_RAY_PARALLEL=2};
extern u8 *func_80020050(tmd_prim_t *,u8 *,s32 *,vec3s_t *,u32 *);
extern void OuterProduct10(sdk_vector_t *,sdk_vector_t *,sdk_vector_t *);
extern void Square0(sdk_vector_t *,sdk_vector_t *);
extern s32 SquareRoot0(s32);
#define collision_abs(x) ((x)<0?~(x)+1:(x))
s32 func_8001F8B8(void *self, s32 *best, model_point_t *hitOut, s32 *height,
    const model_point_t *origin, const model_point_t *end) {
    model_point_t tri[4];
    sdk_vector_t plane;
    collision_ray_t ray;
    model_point_t hit;
    s32 nverts;
    u32 count;
    u8 *p;
    s32 found;

    count = 0;
    *best = 0x7FFFFFFF;
    ray.org.x = origin->x;
    ray.org.y = origin->y;
    ray.org.z = origin->z;
    ray.dir.x = end->x - origin->x;
    ray.dir.y = end->y - origin->y;
    ray.dir.z = end->z - origin->z;
    found = 0;
    while ((p = func_80020050((tmd_prim_t *)self, p, &nverts, tri, &count)) != NULL) {
        /* MATCHING: these are declared in the loop body, which puts them on
         * the stack after nverts and count. */
        sdk_vector_t unused; /* MATCHING: never read; keeps retail's stack layout */
        sdk_svector_t e1;
        sdk_svector_t e2;
        sdk_vector_t cross;
        sdk_vector_t edge1;
        sdk_vector_t edge2;
        sdk_vector_t quot;
        sdk_vector_t work;
        sdk_vector_t dirVec;
        sdk_vector_t dirSq;
        collision_scratch_t scratch;
        s32 dist[2]; /* MATCHING: an array, so it lives on the stack (dist[1] unused) */
        s32 frac;
        s32 q;
        s32 hi;
        s32 t;
        s16 *minx; /* MATCHING: the six box-field pointers give retail's stack size */
        s16 *miny;
        s16 *minz;
        s16 *maxx;
        s16 *maxy;
        s16 *maxz;
        model_point_t *v;
        s32 i;

        e1.x = tri[1].x - tri[0].x;
        e1.y = tri[1].y - tri[0].y;
        e1.z = tri[1].z - tri[0].z;
        e2.x = tri[2].x - tri[0].x;
        e2.y = tri[2].y - tri[0].y;
        e2.z = tri[2].z - tri[0].z;
        edge1.x = e1.x;
        edge1.y = e1.y;
        edge1.z = e1.z;
        edge2.x = e2.x;
        edge2.y = e2.y;
        edge2.z = e2.z;
        OuterProduct10(&edge1, &edge2, &cross);
        plane.x = cross.x;
        plane.y = cross.y;
        plane.z = cross.z;
        plane.x /= 4096;
        plane.y /= 4096;
        plane.z /= 4096;
        plane.pad = -(tri[0].x * plane.x + tri[0].y * plane.y + tri[0].z * plane.z);
        work.x = ray.dir.x * plane.x + ray.dir.y * plane.y + ray.dir.z * plane.z;
        if (collision_abs(work.x) <= 0) {
            work.y = COLLISION_RAY_PARALLEL;
        } else {
            work.z = ray.org.x * plane.x + ray.org.y * plane.y + ray.org.z * plane.z;
            work.z += plane.pad;
            cross.x = work.x;
            cross.y = 1;
            quot.x = -work.z;
            quot.y = 1;
            quot.z = quot.x * cross.y;
            quot.pad = quot.y * cross.x;
            if (collision_abs(quot.pad) >= 4096) {
                quot.z /= 4096;
                quot.pad /= 4096;
            }
            frac = collision_abs(quot.z % quot.pad) << 16;
            q = quot.z / quot.pad;
            if (q != 0) {
                hi = q << 16;
            } else {
                hi = (quot.z * quot.pad) & 0x80000000;
            }
            t = hi | (frac / collision_abs(quot.pad));
            if (t < 0) {
                work.y = COLLISION_RAY_MISS;
            } else {
                dirVec.x = ray.dir.x;
                dirVec.y = ray.dir.y;
                dirVec.z = ray.dir.z;
                edge2.x = (ray.dir.x * t) >> 16;
                edge1.x = ray.org.x + edge2.x;
                edge2.x = edge1.x - ray.org.x;
                edge2.y = (ray.dir.y * t) >> 16;
                edge1.y = ray.org.y + edge2.y;
                edge2.y = edge1.y - ray.org.y;
                edge2.z = (ray.dir.z * t) >> 16;
                edge1.z = ray.org.z + edge2.z;
                edge2.z = edge1.z - ray.org.z;
                Square0(&dirVec, &dirSq);
                work.x = dirSq.x + dirSq.y + dirSq.z;
                work.x = SquareRoot0(work.x);
                Square0(&edge2, &scratch.v);
                work.z = scratch.v.x + scratch.v.y + scratch.v.z;
                work.z = SquareRoot0(work.z);
                if (work.x >= work.z) {
                    dist[0] = work.z;
                    work.y = COLLISION_RAY_HIT;
                    hit.x = edge1.x;
                    hit.y = edge1.y;
                    hit.z = edge1.z;
                } else {
                    work.y = COLLISION_RAY_MISS;
                }
            }
        }
        if (work.y != COLLISION_RAY_HIT) {
            continue;
        }
        minx = &scratch.b.min.x;
        miny = &scratch.b.min.y;
        minz = &scratch.b.min.z;
        maxx = &scratch.b.max.x;
        maxy = &scratch.b.max.y;
        maxz = &scratch.b.max.z;
        v = tri;
        scratch.b.min = *v;
        scratch.b.max = scratch.b.min;
        for (i = 0; i < nverts - 1; i++) {
            v++;
            if (v->x < *minx)
                *minx = v->x;
            if (v->y < *miny)
                *miny = v->y;
            if (v->z < *minz)
                *minz = v->z;
            if (*maxx < v->x)
                *maxx = v->x;
            if (*maxy < v->y)
                *maxy = v->y;
            if (*maxz < v->z)
                *maxz = v->z;
        }
        if (hit.x < scratch.b.min.x - 24 || hit.y < scratch.b.min.y - 24 ||
            hit.z < scratch.b.min.z - 24 || scratch.b.max.x + 24 < hit.x ||
            scratch.b.max.y + 24 < hit.y || scratch.b.max.z + 24 < hit.z) {
            continue;
        }
        found = 1;
        if (dist[0] < *best) {
            *best = dist[0];
            *hitOut = hit;
            if (height != NULL) {
                *height = hit.y - scratch.b.min.y;
            }
        }
    }
    return found;
}

#undef collision_abs


typedef struct {
    u8 *vertices;
    u32 vertex_count;
    void *normals;
    u32 normal_count;
    u8 *primitives;
    u32 primitive_count;
} tmd_geometry_t;
/* Decode one TMD triangle or quad into its referenced vertices. */
u8 *func_80020050(tmd_prim_t *This, u8 *cursor, s32 *count, vec3s_t *points, u32 *index) {
    s32 indices[4];
    tmd_geometry_t *geometry = (tmd_geometry_t *) This->m_Unk3;
    /* The original leaves length unspecified for unsupported primitive codes. */
    s32 length;
    s32 i;
    u8 *vertices;
    if (geometry->primitive_count == 0 || *index >= geometry->primitive_count) return NULL;
    if (*index == 0) cursor = geometry->primitives;
    *count = 4;
    switch (cursor[3]) {
    case 0x20: case 0x22:
        if (cursor[2] & 4) {
            indices[0] = *(u16 *) (cursor + 0x12);
            indices[1] = *(u16 *) (cursor + 0x14);
            indices[2] = *(u16 *) (cursor + 0x16);
            length = 0x18;
        } else {
            indices[0] = *(u16 *) (cursor + 0xA);
            indices[1] = *(u16 *) (cursor + 0xC);
            indices[2] = *(u16 *) (cursor + 0xE);
            length = 0x10;
        }
        *count = 3;
        break;
    case 0x21: case 0x23:
        indices[0] = *(u16 *) (cursor + 0x8);
        indices[1] = *(u16 *) (cursor + 0xA);
        indices[2] = *(u16 *) (cursor + 0xC);
        length = 0x10;
        *count = 3;
        break;
    case 0x24: case 0x26:
        indices[0] = *(u16 *) (cursor + 0x12);
        indices[1] = *(u16 *) (cursor + 0x14);
        indices[2] = *(u16 *) (cursor + 0x16);
        length = 0x18;
        *count = 3;
        break;
    case 0x25: case 0x27:
        indices[0] = *(u16 *) (cursor + 0x14);
        indices[1] = *(u16 *) (cursor + 0x16);
        indices[2] = *(u16 *) (cursor + 0x18);
        length = 0x1C;
        *count = 3;
        break;
    case 0x28: case 0x2A:
        if (cursor[2] & 4) {
            indices[0] = *(u16 *) (cursor + 0x16);
            indices[1] = *(u16 *) (cursor + 0x18);
            indices[2] = *(u16 *) (cursor + 0x1A);
            indices[3] = *(u16 *) (cursor + 0x1C);
            length = 0x20;
        } else {
            indices[0] = *(u16 *) (cursor + 0xA);
            indices[1] = *(u16 *) (cursor + 0xC);
            indices[2] = *(u16 *) (cursor + 0xE);
            indices[3] = *(u16 *) (cursor + 0x10);
            length = 0x14;
        }
        break;
    case 0x29: case 0x2B:
        indices[0] = *(u16 *) (cursor + 0x8);
        indices[1] = *(u16 *) (cursor + 0xA);
        indices[2] = *(u16 *) (cursor + 0xC);
        indices[3] = *(u16 *) (cursor + 0xE);
        length = 0x10;
        break;
    case 0x2C: case 0x2E:
        indices[0] = *(u16 *) (cursor + 0x16);
        indices[1] = *(u16 *) (cursor + 0x18);
        indices[2] = *(u16 *) (cursor + 0x1A);
        indices[3] = *(u16 *) (cursor + 0x1C);
        length = 0x20;
        break;
    case 0x2D: case 0x2F:
        indices[0] = *(u16 *) (cursor + 0x18);
        indices[1] = *(u16 *) (cursor + 0x1A);
        indices[2] = *(u16 *) (cursor + 0x1C);
        indices[3] = *(u16 *) (cursor + 0x1E);
        length = 0x20;
        break;
    case 0x30: case 0x32:
        if (cursor[2] & 4) {
            indices[0] = *(u16 *) (cursor + 0x12);
            indices[1] = *(u16 *) (cursor + 0x16);
            indices[2] = *(u16 *) (cursor + 0x1A);
            length = 0x1C;
        } else {
            indices[0] = *(u16 *) (cursor + 0xA);
            indices[1] = *(u16 *) (cursor + 0xE);
            indices[2] = *(u16 *) (cursor + 0x12);
            length = 0x14;
        }
        *count = 3;
        break;
    case 0x31: case 0x33:
        indices[0] = *(u16 *) (cursor + 0x10);
        indices[1] = *(u16 *) (cursor + 0x12);
        indices[2] = *(u16 *) (cursor + 0x14);
        length = 0x18;
        *count = 3;
        break;
    case 0x34: case 0x36:
        indices[0] = *(u16 *) (cursor + 0x12);
        indices[1] = *(u16 *) (cursor + 0x16);
        indices[2] = *(u16 *) (cursor + 0x1A);
        length = 0x1C;
        *count = 3;
        break;
    case 0x35: case 0x37:
        indices[0] = *(u16 *) (cursor + 0x1C);
        indices[1] = *(u16 *) (cursor + 0x1E);
        indices[2] = *(u16 *) (cursor + 0x20);
        length = 0x24;
        *count = 3;
        break;
    case 0x38: case 0x3A:
        length = 0x18;
        if (!(cursor[2] & 4)) {
            indices[0] = *(u16 *) (cursor + 0xA);
            indices[1] = *(u16 *) (cursor + 0xE);
            indices[2] = *(u16 *) (cursor + 0x12);
            indices[3] = *(u16 *) (cursor + 0x16);
            length = 0x18;
            break;
        }
        goto quad_3c;
    case 0x39: case 0x3B:
        indices[0] = *(u16 *) (cursor + 0x14);
        indices[1] = *(u16 *) (cursor + 0x16);
        indices[2] = *(u16 *) (cursor + 0x18);
        indices[3] = *(u16 *) (cursor + 0x1A);
        length = 0x1C;
        break;
    case 0x3C: case 0x3E:
    quad_3c:
        indices[0] = *(u16 *) (cursor + 0x16);
        indices[1] = *(u16 *) (cursor + 0x1A);
        indices[2] = *(u16 *) (cursor + 0x1E);
        indices[3] = *(u16 *) (cursor + 0x22);
        length = 0x24;
        break;
    case 0x3D: case 0x3F:
        indices[0] = *(u16 *) (cursor + 0x24);
        indices[1] = *(u16 *) (cursor + 0x26);
        indices[2] = *(u16 *) (cursor + 0x28);
        indices[3] = *(u16 *) (cursor + 0x2A);
        length = 0x2C;
        break;
    default:
        *count = 0;
        break;
    }
    vertices = ((tmd_geometry_t *) This->m_Unk3)->vertices;
    for (i = 0;i<*count;i++) {
        *points = *(vec3s_t *) (vertices + (indices[i] << 3));
        points++;
    }
    (*index)++;
    return cursor + length;
}

void func_800204D0(s32 arg0, s32 *arg1) {
    u16 *p = *(u16 **) (*(u32 *) (arg0 + 0x10) + 0x10);
    s32 v;

    p[3] += arg1[0] / 16;
    v = arg1[1];
    p[3] += v << 6;
}

s32 func_80020510(s32 arg0, s16 *arg1) {
    u16 *p = *(u16 **) (*(u32 *) (arg0 + 0x10) + 0x10);
    s32 r;

    p[3] = arg1[0] / 16;
    r = arg1[1] << 6;
    p[3] += r;
    return r;
}
