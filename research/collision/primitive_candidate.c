/*
 * UNACCEPTED matching-C research fragment for func_8001F8B8.
 * Insert at its INCLUDE_ASM in src/file/tmd_prim_geom.c; the surrounding
 * translation unit supplies common.h, tmd_prim_t and vec3s_t.
 * The complete private executable differs in 22 bounding-box stack offsets.
 * This file is excluded from the canonical build and C-recovery counts.
 */
typedef vec3s_t model_point_t;
typedef struct {s16 x,y,z,pad;} sdk_svector_t;
typedef struct {s32 x,y,z,pad;} sdk_vector_t;
typedef struct {s32 x,y,z,d;} collision_plane_t;
typedef struct {s32 numerator,denominator;} collision_fraction_t;
typedef struct {model_point_t min,max;} collision_bounds_t;

extern u8 *func_80020050(tmd_prim_t *,u8 *,s32 *,vec3s_t *,u32 *);
extern void OuterProduct10(sdk_vector_t *,sdk_vector_t *,sdk_vector_t *);
extern void Square0(sdk_vector_t *,sdk_vector_t *);
extern s32 SquareRoot0(s32);

#define collision_abs(value) ((value)>=0?(value):~(value)+1)

static inline s32 fraction_fixed(collision_fraction_t *ratio_ptr) {
#define ratio (*ratio_ptr)
    s32 remainder=ratio.numerator%ratio.denominator;
    s32 fraction=collision_abs(remainder)<<16;
    s32 quotient=ratio.numerator/ratio.denominator;
    s32 whole=quotient!=0?quotient<<16:(ratio.numerator*ratio.denominator)&0x80000000;
    return whole|(fraction/collision_abs(ratio.denominator));
#undef ratio
}

static inline void polygon_bounds(model_point_t *points,s32 *count_ptr,collision_bounds_t *bounds) {
    s32 i;
    model_point_t *point;
    s16 *min_x,*min_y,*min_z,*max_x,*max_y,*max_z;
    point=points;
    bounds->min=points[0];
    bounds->max=bounds->min;
    i=0;
    min_x=&bounds->min.x;
    min_y=&bounds->min.y;
    min_z=&bounds->min.z;
    max_x=&bounds->max.x;
    max_y=&bounds->max.y;
    max_z=&bounds->max.z;
    if(i<*count_ptr-1) {
        do {
            point++;
            if(point->x<*min_x)*min_x=point->x;
            if(point->y<*min_y)*min_y=point->y;
            if(point->z<*min_z)*min_z=point->z;
            if(*max_x<point->x)*max_x=point->x;
            if(*max_y<point->y)*max_y=point->y;
            if(*max_z<point->z)*max_z=point->z;
            i++;
        } while(i<*count_ptr-1);
    }
}

static inline s32 scale_segment(s32 coordinate,s32 fixed) {
    return (coordinate*fixed)>>16;
}

static inline void publish_hit(model_point_t *hit,sdk_vector_t *intersection,s32 value,s32 *distance) {
    hit->x=intersection->x;
    hit->y=intersection->y;
    hit->z=intersection->z;
    *distance=value;
}

s32 func_8001F8B8(void *model,s32 *nearest,model_point_t *output,s32 *height,
                 model_point_t *segment_start,model_point_t *segment_end) {
    model_point_t points[4];
    collision_plane_t plane;
    model_point_t start_delta[2],hit;
#define start start_delta[0]
#define delta start_delta[1]
    s32 count;
    u32 index=0;
    /* Native first-entry S1 is unspecified; index zero makes the decoder ignore it. */
    u8 *cursor;
    s32 result=0;
    s32 status;
    *nearest=0x7FFFFFFF;
    start.x=segment_start->x;
    start.y=segment_start->y;
    start.z=segment_start->z;
    delta.x=segment_end->x-segment_start->x;
    delta.y=segment_end->y-segment_start->y;
    delta.z=segment_end->z-segment_start->z;
    while(1) {
        cursor=func_80020050(model,cursor,&count,points,&index);
        if(cursor==NULL)break;
        {
            collision_bounds_t bounds;
            sdk_svector_t edge1,edge2;
            union {sdk_vector_t normal;collision_fraction_t fraction;} normal;
            sdk_vector_t intersection,offset;
            collision_fraction_t numerator,ratio;
            struct {s32 dot,status,start_dot;} state;
            s32 fixed;
            sdk_vector_t delta_wide,delta_square,square;
            s32 distance[1];

            edge1.x=points[1].x-points[0].x;
            edge1.y=points[1].y-points[0].y;
            edge1.z=points[1].z-points[0].z;
            edge2.x=points[2].x-points[0].x;
            edge2.y=points[2].y-points[0].y;
            edge2.z=points[2].z-points[0].z;
            intersection.x=edge1.x;
            intersection.y=edge1.y;
            intersection.z=edge1.z;
            offset.x=edge2.x;
            offset.y=edge2.y;
            offset.z=edge2.z;
            OuterProduct10(&intersection,&offset,&normal.normal);
            plane.x=normal.normal.x;
            plane.y=normal.normal.y;
            plane.z=normal.normal.z;
            plane.x/=0x1000;
            plane.y/=0x1000;
            plane.z/=0x1000;
            plane.d=-(points[0].x*plane.x+points[0].y*plane.y+points[0].z*plane.z);

            state.dot=delta.x*plane.x+delta.y*plane.y+delta.z*plane.z;
            if(collision_abs(state.dot)<1) {
                state.status=2;
                goto segment_complete;
            }
            normal.fraction.numerator=state.dot;
            normal.fraction.denominator=1;
            state.start_dot=start.x*plane.x+start.y*plane.y+start.z*plane.z;
            state.start_dot+=plane.d;
            numerator.numerator=-state.start_dot;
            numerator.denominator=1;
            ratio.numerator=-state.start_dot;
            ratio.denominator=state.dot;
            if(collision_abs(state.dot)>=0x1000) {
                ratio.numerator/=0x1000;
                ratio.denominator/=0x1000;
            }
            fixed=fraction_fixed(&ratio);
            if(fixed<0) {
                state.status=0;
                goto segment_complete;
            }
            delta_wide.x=delta.x;
            delta_wide.y=delta.y;
            delta_wide.z=delta.z;
            offset.x=scale_segment(delta_wide.x,fixed);
            offset.y=scale_segment(delta_wide.y,fixed);
            offset.z=scale_segment(delta_wide.z,fixed);
            intersection.x=start.x+offset.x;
            intersection.y=start.y+offset.y;
            intersection.z=start.z+offset.z;
            offset.x=intersection.x-start.x;
            offset.y=intersection.y-start.y;
            offset.z=intersection.z-start.z;
            Square0(&delta_wide,&delta_square);
            state.dot=delta_square.x+delta_square.y+delta_square.z;
            state.dot=SquareRoot0(state.dot);
            Square0(&offset,&square);
            state.start_dot=square.x+square.y+square.z;
            state.start_dot=SquareRoot0(state.start_dot);
            if(state.dot>=state.start_dot) {
                publish_hit(&hit,&intersection,state.start_dot,distance);
                state.status=1;
            } else {
                state.status=0;
            }
segment_complete:
            status=state.status;

            if(status==1) {
                polygon_bounds(points,&count,&bounds);
                /* The original uses an expanded AABB, including points outside a triangle. */
                if(hit.x>=bounds.min.x-0x18 && hit.y>=bounds.min.y-0x18 && hit.z>=bounds.min.z-0x18 &&
                   hit.x<=bounds.max.x+0x18 && hit.y<=bounds.max.y+0x18 && hit.z<=bounds.max.z+0x18) {
                    result=1;
                    if(distance[0]<*nearest) {
                        *nearest=distance[0];
                        *output=hit;
                        if(height!=NULL)*height=hit.y-bounds.min.y;
                    }
                }
            }
        }
    }
    return result;
}

#undef start
#undef delta
#undef collision_abs
