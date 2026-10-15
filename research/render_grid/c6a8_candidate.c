/*
 * Unaccepted research fragment for func_8004C6A8.
 * Insert into the complete render_context.c unit with prepare_candidate.py.
 * It relies on that unit's existing func_8004C1C0_out_t declaration.
 * The current candidate differs in two inclusive-edge arithmetic instructions.
 * Complete executable equality is required before any source promotion.
 */
typedef struct {
    s16 rotation[3][3];
    s16 align;
    vec3d_t vector;
} render_grid_matrix_t;

extern render_grid_matrix_t D_8008E98C;
void RotMatrix(s16 *, render_grid_matrix_t *);
void ApplyMatrixLV(render_grid_matrix_t *, vec3d_t *, vec3d_t *);
void func_8004C93C(render_context_t *);

static inline void render_grid_set_dimensions(render_context_t *This,
                                              s32 rows, s32 columns) {
    This->m_Unk31 = rows;
    This->m_Unk32 = columns;
}

static inline s32 *render_grid_columns_after_rows(render_context_t *This,
                                                 s32 rows) {
    This->m_Unk31 = rows;
    return &This->m_Unk32;
}

void func_8004C6A8(render_context_t *This, s32 width, s32 height) {
    func_8004C1C0_out_t info;
    render_grid_matrix_t matrix;
    s32 orientation;
    s16 *angles;
    s16 *rotation;
    s16 angle;
    s32 x, z;
    s32 correction;
    s32 origin;

    angles = *(s16 **) ((u8 *) *(void **) (This->m_Unk26 + 0x14) + 0x44);
    rotation = angles + 8;
    This->vtable->Unk66(This, &info, 0);
    x = info.dx;
    z = info.dz;
    angle = angles[9];
    if (angle < 0) {
        angle += 0x1000;
    }
    matrix = D_8008E98C;
    matrix.vector.x = 0;
    matrix.vector.y = 0;
    matrix.vector.z = This->m_Unk28;
    RotMatrix(rotation, &matrix);
    ApplyMatrixLV(&matrix, &matrix.vector, &matrix.vector);

    if ((u16) (angle - 0x200) < 0x400 || (u16) (angle - 0xA00) < 0x400) {
        correction = matrix.vector.z;
        render_grid_set_dimensions(This, height, width);
        origin = matrix.vector.x > 0 ? x : x + (1 - width);
        This->m_Unk30_1 = origin;
        if (matrix.vector.z > 0) {
            This->m_Unk30_2 = z - *(u16 *) &This->m_Unk29_1 - 1;
        } else {
            This->m_Unk30_2 = z - *(u16 *) &This->m_Unk29_1 + 1;
        }
        orientation = 0;
    } else if ((u16) (angle - 0x600) < 0x400 ||
               (u16) (angle - 0x200) >= 0xC00) {
        correction = matrix.vector.x;
        *render_grid_columns_after_rows(This, width) = height;
        if (matrix.vector.x > 0) {
            This->m_Unk30_1 = x - *(u16 *) &This->m_Unk29_1 - 1;
        } else {
            This->m_Unk30_1 = x - *(u16 *) &This->m_Unk29_1 + 1;
        }
        origin = matrix.vector.z > 0 ? z : z - height + 1;
        This->m_Unk30_2 = origin;
        orientation = 1;
    }
    correction >>= 11;
    if (correction >= *(s16 *) &This->m_Unk29_1) {
        correction = *(s16 *) &This->m_Unk29_1 - 1;
    }
    if (correction <= -*(s16 *) &This->m_Unk29_1) {
        correction = -*(s16 *) &This->m_Unk29_1 + 1;
    }
    if (orientation != 0) {
        This->m_Unk30_1 += correction;
    } else {
        This->m_Unk30_2 += correction;
    }
    func_8004C93C(This);
}
