#define COLLISION_ABI_CHECK(name, expression) typedef char collision_abi_##name[(expression) ? 1 : -1]
COLLISION_ABI_CHECK(pointer_width, sizeof(void *) == 4);
COLLISION_ABI_CHECK(word_width, sizeof(s32) == 4);
COLLISION_ABI_CHECK(word_signed, (s32)-1 < 0);
COLLISION_ABI_CHECK(halfword_width, sizeof(s16) == 2);
COLLISION_ABI_CHECK(halfword_signed, (s16)-1 < 0);
COLLISION_ABI_CHECK(point_size, sizeof(vec3d_16_t) == 6);
COLLISION_ABI_CHECK(point_alignment, __alignof__(vec3d_16_t) == 2);
COLLISION_ABI_CHECK(point_x, (u32)&((vec3d_16_t *)0)->x == 0);
COLLISION_ABI_CHECK(point_y, (u32)&((vec3d_16_t *)0)->y == 2);
COLLISION_ABI_CHECK(point_z, (u32)&((vec3d_16_t *)0)->z == 4);
COLLISION_ABI_CHECK(transform_size, sizeof(vec4d_16_t) == 8);
COLLISION_ABI_CHECK(transform_x, (u32)&((vec4d_16_t *)0)->x == 0);
COLLISION_ABI_CHECK(transform_y, (u32)&((vec4d_16_t *)0)->y == 2);
COLLISION_ABI_CHECK(transform_z, (u32)&((vec4d_16_t *)0)->z == 4);
COLLISION_ABI_CHECK(request_size, sizeof(collision_api_request_t) == 24);
COLLISION_ABI_CHECK(request_model, (u32)&((collision_api_request_t *)0)->model == 0);
COLLISION_ABI_CHECK(request_start, (u32)&((collision_api_request_t *)0)->start == 4);
COLLISION_ABI_CHECK(request_end, (u32)&((collision_api_request_t *)0)->end == 8);
COLLISION_ABI_CHECK(request_hit, (u32)&((collision_api_request_t *)0)->hit == 12);
COLLISION_ABI_CHECK(request_nearest, (u32)&((collision_api_request_t *)0)->nearest == 16);
COLLISION_ABI_CHECK(request_height, (u32)&((collision_api_request_t *)0)->height == 20);
#undef COLLISION_ABI_CHECK
