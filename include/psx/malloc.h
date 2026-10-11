#ifndef LSD_PSX_MALLOC_H
#define LSD_PSX_MALLOC_H

#include <types.h>

void *psyq_malloc_malloc(u32 size);
void psyq_malloc_free(void *pointer);

#endif
