#ifndef LSD_OBJECT_MATH_H
#define LSD_OBJECT_MATH_H

#include <common.h>

/* Transform one three-word local point and add the object's world position.
 * Both original callers pass zero for the ignored fourth argument. */
void transform_local_to_world(void *object, vec3d_t *world_point, const void *local_point, s32 unused);

#endif // LSD_OBJECT_MATH_H
