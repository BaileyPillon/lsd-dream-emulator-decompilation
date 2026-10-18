#include "common.h"

#include "base/base.h"
#include "file/file_buf.h"
#include "graphics/display.h"

typedef struct cd_file_request {
    /* 0x00 */ s32 m_Cancel;
    /* 0x04 */ s32 m_Unk1;
    /* 0x08 */ s32 m_Unk2;
    /* 0x0C */ s32 m_FileBuf;
    /* 0x10 */ s32 m_Unk4;
    /* 0x14 */ s32 m_Unk5;
    /* 0x18 */ s32 m_Unk6;
    /* 0x1C */ struct cd_file_request *m_Prev;
    /* 0x20 */ struct cd_file_request *m_Next;
} cd_file_request_t;

typedef struct unk_disc_loc {
    u8 minute;
    u8 second;
    u8 sector;
    u8 track;
} unk_disc_loc_t;

typedef struct unk_disc_file {
    unk_disc_loc_t m_Pos;
    s32 m_Size;
    char m_Name[16];
} unk_disc_file_t;

typedef struct unk_disc_record {
    char m_Name[0x14];
    unk_disc_loc_t m_Pos;
    s32 m_Size;
} unk_disc_record_t;

extern void VSyncCallback();
display_t *get_display(void);
extern const char *get_current_data_folder(void);
extern char *strcpy(char *, char *);
extern char *strcat(char *, char *);
extern char *strstr(char *, char *);
extern s32 CdSetDebug(s32);
extern s32 CdControlB(s32, u8 *, s32 *);
extern s32 CdControl(s32, u8 *, s32);
extern s32 CdControlF(s32, u8 *);
extern s32 CdSync(s32, u8 *);
extern s32 CdReadSync(s32, u8 *);
extern s32 CdFlush();
extern s32 CdPosToInt(u8 *);
extern void CdIntToPos(s32, u8 *);
extern s32 CdSearchFile(void *, char *);
extern u8 D_8006D574[];
extern s32 func_80029274(s32 sectors, void *destination, s32 mode);

void *cd_file_driver_get_vtable(void);
void cd_file_driver_init(void);
void cd_file_driver_begin_read(s32 arg0, s32 arg1);
s32 cd_file_driver_find_disc_record(s32 arg0);
s8 *cd_file_driver_build_path(s8 *arg0, s8 *arg1);
void cd_file_driver_end_read(void);
void cd_file_driver_queue_request(file_buf_t *arg0, s32 arg1, s32 arg2, s32 arg3, s32 arg4);
s32 cd_file_driver_find_disc_record_index(s32 arg0);
void cd_file_driver_reset_cache(file_buf_t *This);
s32 cd_file_driver_get_aligned_size(file_buf_t *This);
s32 cd_file_driver_get_disc_record(s32 arg0);
void cd_file_driver_free_request(cd_file_request_t *node);
cd_file_request_t *cd_file_driver_alloc_request(void);

s32 cd_file_driver_tick(void);
void cd_file_driver_lookup_file(file_buf_t *This, s8 *arg1);
void cd_file_driver_lock(void);
void cd_file_driver_unlock(void);
void cd_file_driver_stop_read(void);
void cd_file_driver_read_state1(void);
void cd_file_driver_read_state2(void);
void cd_file_driver_set_read_result(s32 arg0);
s32 cd_file_driver_read_sectors(file_buf_t *file, void *destination, u32 bytes);

extern s32 g_CdInitialized;
extern s32 g_CdCallbackInstalled;
extern char g_CdPathSuffix[];
extern s32 g_CdFrameActive;
extern s32 g_CdFrameParam;
extern s32 g_CdReadBusy;
extern s32 g_CdDiscTable;
extern s32 g_CdDiscCount;
extern s32 g_CdReadIdle;
extern s32 g_CdReadParam;
extern s32 g_CdReadState;
extern s32 g_CdReadPos;
extern s32 g_CdReadTarget;
extern s32 g_CdLocked;
extern s32 g_CdCallbackActive;
extern cd_file_request_t *g_CdRequestList;
extern s32 g_CdReadPhase;
extern u32 g_CdReadDest;
extern s32 g_CdReadLba;
extern s32 g_CdTimeoutCounter;
extern s32 g_CdFrameMode;
extern s32 g_CD_FILE_DRIVER_VTABLE[];

void *cd_file_driver_create(void) {
    void *mem = memory_allocate_mem(0x2C);

    if (mem != NULL) {
        ((file_buf_vtable_t *) cd_file_driver_get_vtable())->Construct(mem);
        return mem;
    }
    return NULL;
}

void cd_file_driver_construct(file_buf_t *This) {
    file_buf_get_vtable()->Construct(This);
    This->vtable = cd_file_driver_get_vtable();
    This->m_Unk9 = 0;
    cd_file_driver_init();
}

void cd_file_driver_cleanup(file_buf_t *This) {
    This->vtable->Unk28(This);
    This->vtable->file_buf_release(This);
}

void cd_file_driver_unk15(void) {
}

void cd_file_driver_open(file_buf_t *This, s32 arg1, s32 arg2, s32 arg3) {
    s8 path[0x40];
    unk_disc_file_t file;
    s32 status;

    if (g_CdFrameActive == 0 && g_CdFrameParam == 0) {
        cd_file_driver_lookup_file(This, (s8 *)arg1);
        return;
    }
    cd_file_driver_lock();
    if (This->m_Unk9 != 0) {
        if (g_CdReadBusy == 0 && This->m_Unk2 == 0) {
            cd_file_driver_begin_read(1, 1);
            if (g_CdFrameActive != 0) {
                g_CdReadPos = (s32) cd_file_driver_find_disc_record(arg1);
                if (g_CdReadPos == 0) {
                    return;
                }
                *(unk_disc_loc_t *) ((u8 *) This + 0x18) = ((unk_disc_record_t *) g_CdReadPos)->m_Pos;
                This->m_Unk6 = ((unk_disc_record_t *) g_CdReadPos)->m_Size;
                g_CdReadPhase = 1;
                This->m_Unk2 = 1;
            } else {
                cd_file_driver_build_path(path, (s8 *) arg1);
                while (CdSearchFile(&file, path) == 0) {
                }
                *(unk_disc_loc_t *) ((u8 *) This + 0x18) = file.m_Pos;
                This->m_Unk6 = file.m_Size;
                do {
                    CdControl(2, (u8 *) This + 0x18, 0);
                    do {
                        status = CdSync(0, 0);
                    } while (status == 0);
                } while (status == 5);
                This->m_Unk2 = 1;
                cd_file_driver_end_read();
            }
        }
    } else {
        cd_file_driver_queue_request(This, cd_file_driver_find_disc_record_index(arg1), 2, arg2, arg3);
    }
    cd_file_driver_unlock();
}

void cd_file_driver_close(file_buf_t *This) {
    if (g_CdFrameActive == 0 && g_CdFrameParam == 0) {
        cd_file_driver_reset_cache(This);
    } else {
        cd_file_driver_lock();
        if (This->m_Unk9 != 0) {
            if (g_CdReadBusy == 0) {
                cd_file_driver_begin_read(0, 0);
                This->m_Unk2 = 0;
                cd_file_driver_end_read();
            }
        } else {
            cd_file_driver_queue_request(This, 0, 3, 0, 0);
        }
        cd_file_driver_unlock();
    }
}

s32 cd_file_driver_seek(file_buf_t *This, u32 arg1, s32 arg2) {
    u32 temp_v0;
    u32 var_s0;
    s32 status;

    if (g_CdFrameActive == 0 && g_CdFrameParam == 0) {
        return cd_file_driver_get_aligned_size(This);
    }

    cd_file_driver_lock();
    if (This->m_Unk9 != 0) {
        if (g_CdReadBusy == 0 && This->m_Unk2 != 0) {
            cd_file_driver_begin_read(2, 1);
            var_s0 = arg1 >> 11;
            if (arg1 & 0x7FF) {
                var_s0 += 1;
            }
            CdIntToPos(CdPosToInt((u8 *) &This->m_Unk5) + var_s0, D_8006D574);
            if (arg2 == 0) {
                if (g_CdFrameActive != 0) {
                    g_CdReadPos = (s32) D_8006D574 - 0x14;
                    g_CdReadPhase = 1;
                } else {
                    do {
                        CdControl(2, D_8006D574, 0);
                        do {
                            status = CdSync(0, 0);
                        } while (status == 0);
                    } while (status == 5);
                    cd_file_driver_end_read();
                }
            } else {
                cd_file_driver_end_read();
                cd_file_driver_unlock();
                temp_v0 = This->m_Unk6;
                if (temp_v0 & 0x7FF) {
                    return ((temp_v0 >> 11) + 1) << 11;
                }
                return temp_v0;
            }
        }
    } else {
        cd_file_driver_queue_request(This, 0, 4, arg1, arg2);
    }
    cd_file_driver_unlock();
    return 0;
}

void cd_file_driver_unk19(void) {
}

s32 cd_file_driver_read(file_buf_t *This, s32 arg1, u32 arg2) {
    s32 status;

    if (g_CdFrameActive == 0 && g_CdFrameParam == 0) {
        cd_file_driver_read_sectors(This, (void *)arg1, arg2);
        return 0;
    }
    cd_file_driver_lock();
    if (This->m_Unk9 != 0) {
        if (g_CdReadBusy == 0 && This->m_Unk2 != 0) {
            cd_file_driver_begin_read(3, 7);
            if (g_CdFrameActive != 0) {
                g_CdReadDest = arg2 >> 11;
                g_CdReadLba = arg1;
                g_CdReadPhase = 1;
            } else {
            retry2:
                func_80029274(arg2 >> 11, (void *)arg1, 0x80);
                do {
                    status = CdReadSync(0, 0);
                } while (status > 0);
                if (status == -1) {
                    goto retry2;
                }
                cd_file_driver_end_read();
            }
        }
    } else {
        cd_file_driver_queue_request(This, 0, 5, arg1, arg2);
    }
    cd_file_driver_unlock();
    return 0;
}

extern void file_buf_load(file_buf_t *, s32);

void cd_file_driver_unk21(file_buf_t *arg0, s32 arg1) {
    unk_disc_record_t *record;
    s32 size, status;
    if (g_CdFrameActive == 0 && g_CdFrameParam == 0) {
        file_buf_load(arg0, arg1);
        arg0->m_Flags |= 0x200;
        arg0->vtable->Unk24(arg0);
        return;
    }
    cd_file_driver_lock();
    if (arg0->m_Unk9 != 0) {
        if (g_CdReadBusy == 0 && (arg0->m_Buffer == 0 || arg0->m_NoFree != 0)) {
            cd_file_driver_begin_read(4, 1);
            g_CdReadTarget = g_CdReadPos;
            record = (unk_disc_record_t *)cd_file_driver_find_disc_record(arg1);
            g_CdReadPos = (s32)record;
            if (record == NULL) {
                return;
            }
            g_CdReadDest = (u32)record->m_Size >> 11;
            if (record->m_Size & 0x7FF) {
                g_CdReadDest += 1;
            }
            size = g_CdReadDest << 11;
            if (arg0->m_Buffer == 0) {
                void *temp = memory_allocate_mem(size);
                if (temp == NULL) {
                    arg0->vtable->Close(arg0);
                    return;
                }
                g_CdReadLba = (s32)temp;
                arg0->m_Buffer = temp;
            } else {
                g_CdReadLba = (s32)arg0->m_Buffer;
            }
            if (g_CdFrameActive != 0) {
                arg0->m_Size = size;
                g_CdReadPhase = 2;
            } else {
sync_read:
                do {
                    CdControl(2, (u8 *)(g_CdReadPos + 0x14), 0);
                    do {
                        status = CdSync(0, 0);
                    } while (status == 0);
                } while (status == 5);
                func_80029274(g_CdReadDest, arg0->m_Buffer, 0x80);
                do { status = CdReadSync(0, 0); } while (status > 0);
                if (status == -1) {
                    goto sync_read;
                }
                arg0->m_Size = size;
                g_CdRequestList->m_Cancel = 1;
                cd_file_driver_end_read();
            }
        }
    } else {
        cd_file_driver_queue_request(arg0, cd_file_driver_find_disc_record_index(arg1), 7, 0, 0);
    }
    cd_file_driver_unlock();
}


void cd_file_driver_unk25(void) {
    cd_file_request_t *req;
    file_buf_t *buf;
    s32 type;

    cd_file_driver_lock();
    req = g_CdRequestList;
    if (req == NULL) {
        goto end;
    }
    buf = (file_buf_t *)req->m_FileBuf;
    type = req->m_Unk2;
    if (req->m_Cancel != 0) {
        goto cancel;
    }
    buf->m_Unk9 = 1;
    switch (type) {
    case 2:
        buf->vtable->Open(buf, cd_file_driver_get_disc_record(type = req->m_Unk4), req->m_Unk5, req->m_Unk6);
        break;
    case 3:
        buf->vtable->Close(buf);
        break;
    case 4:
        buf->vtable->Seek(buf, req->m_Unk5, req->m_Unk6);
        break;
    case 5:
        buf->vtable->Read(buf, req->m_Unk5, (u32) req->m_Unk6);
        break;
    case 7:
        buf->vtable->file_buf_load(buf, (void *)cd_file_driver_get_disc_record(type = req->m_Unk4));
        break;
    default:
        break;
    }
    buf->m_Unk9 = 0;
    goto end;

cancel:
    if (g_CdReadIdle == 0) {
        goto end;
    }
    if (req->m_Unk1 != 0) {
        buf->m_Flags |= 1;
    }
    buf->m_Unk7_2 = buf->m_Unk7_2 - 1;
    buf->m_Flags |= 2;
    if (buf->m_Unk7_2 == 0) {
        /* Completion flags are shared with the VSync-driven reader; retain
         * the original separate load and store for this notification. */
        ((volatile file_buf_t *)buf)->m_Flags |= 4;
    }
    switch (type) {
    case 2:
        buf->m_Flags |= 0x10;
        break;
    case 3:
        buf->m_Flags |= 0x20;
        break;
    case 4:
        buf->m_Flags |= 0x40;
        break;
    case 5:
        buf->m_Flags |= 0x80;
        break;
    case 7:
        buf->m_Flags |= 0x200;
        break;
    default:
        break;
    }
    buf->vtable->Unk24(buf);
    cd_file_driver_free_request(req);
    if (g_CdRequestList == 0) {
        buf->vtable->Unk27(buf);
    }
end:
    cd_file_driver_unlock();
}

void cd_file_driver_unk26(file_buf_t *This, s32 path) {
    /* The original executable dereferences saved s2 without initializing it.
     * Keep this local uninitialized for parity; its provenance is unknown. */
    cd_file_request_t *request;

    cd_file_driver_lock();
    if (path != 0) {
        if (g_CdFrameActive != 0) {
            request->m_Unk1 = 1;
            cd_file_driver_queue_request(This, cd_file_driver_find_disc_record_index(path), 7, 0, 0);
        } else {
            This->vtable->file_buf_load(This, (void *)path);
            if (This->m_Unk7_2 == 0) {
                This->m_Flags |= 4;
            }
        }
    }
    cd_file_driver_unlock();
}

void cd_file_driver_unk27(void) {
    cd_file_driver_lock();
    cd_file_driver_stop_read();
    cd_file_driver_unlock();
}

void cd_file_driver_unk28(file_buf_t *arg0) {
    cd_file_request_t *node;
    cd_file_request_t *next;

    cd_file_driver_lock();
    if (g_CdRequestList != NULL && arg0->m_Unk7_2 != 0) {
        arg0->m_Flags = 0;
        if (g_CdRequestList->m_FileBuf == (s32) arg0 && g_CdRequestList->m_Cancel != 0 && g_CdReadIdle == 0) {
            CdFlush();
            cd_file_driver_end_read();
            g_CdReadPos = g_CdReadTarget;
            g_CdReadTarget = 0;
        }
        node = g_CdRequestList;
        if (node != NULL) {
            do {
                next = node->m_Next;
                if (node->m_FileBuf == (s32) arg0) {
                    cd_file_driver_free_request(node);
                    arg0->m_Unk7_2 = arg0->m_Unk7_2 - 1;
                }
                node = next;
            } while (node != NULL);
        }
    }
    cd_file_driver_unlock();
}

void *cd_file_driver_get_vtable(void) {
    return g_CD_FILE_DRIVER_VTABLE;
}

void cd_file_driver_init(void) {
    u8 param;

    if (g_CdInitialized == 0) {
        CdSetDebug(0);
        param = 0x80;
        do {
        } while (CdControlB(0xE, &param, 0) == 0);
        g_CdInitialized = 1;
    }
}

s32 cd_file_driver_is_busy(void) {
    return g_CdReadBusy;
}

s32 cd_file_driver_is_read_idle(void) {
    return g_CdReadIdle;
}

s32 cd_file_driver_get_read_param(void) {
    return g_CdReadParam;
}

s32 cd_file_driver_get_read_state(void) {
    return g_CdReadState;
}

s32 cd_file_driver_get_frame_state(s32 *arg0) {
    if (arg0 != NULL) {
        *arg0 = g_CdFrameParam;
    }
    return g_CdFrameActive;
}

s32 cd_file_driver_frame_setup(s32 arg0, s32 arg1, s32 arg2) {
    display_t *disp;

    if (g_CdReadBusy == 0) {
        if (arg2 == 0) {
            disp = get_display();
            if (g_CdFrameActive == 0) {
                if (arg0 != 0) {
                    disp->vtable->display_set_vsync_callback(disp, cd_file_driver_tick);
                }
            } else {
                if (arg0 == 0) {
                    disp->vtable->display_set_vsync_callback(disp, NULL);
                }
            }
        }
        g_CdFrameMode = arg2;
        g_CdFrameActive = arg0;
        g_CdFrameParam = arg1;
        return 1;
    }
    return 0;
}

void cd_file_driver_set_disc_table(s32 arg0) {
    g_CdDiscTable = arg0;
}

void cd_file_driver_set_disc_count(s32 arg0) {
    g_CdDiscCount = arg0;
}

s32 cd_file_driver_get_disc_count(void) {
    return g_CdDiscCount;
}

extern s32 printf(char *, ...);
extern char g_CdFileNotFoundFileFmt[];

s32 cd_file_driver_search_disc_files(u8 *rec, s32 arg1) {
    s8 path[0x40];
    unk_disc_file_t file;
    u8 *dst;
    u8 *end;
    s32 count;
    s32 result;

    end = rec + arg1 * 0x1C;
    cd_file_driver_init();
    result = 1;
    if (rec < end) {
        dst = rec + 0x18;
        do {
            cd_file_driver_build_path(path, (s8 *)rec);
            count = 0;
            while (CdSearchFile(&file, (char *)path) == 0) {
                count += 1;
                if (count >= 0x65) {
                    printf(g_CdFileNotFoundFileFmt, path);
                    break;
                }
            }
            *(unk_disc_loc_t *)(dst - 4) = file.m_Pos;
            rec += 0x1C;
            *(s32 *)dst = file.m_Size;
            dst += 0x1C;
        } while (rec < end);
        return 1;
    }
    return result;
}


void cd_file_driver_lock(void) {
    g_CdLocked = 1;
}

void cd_file_driver_unlock(void) {
    g_CdLocked = 0;
}

s32 cd_file_driver_tick(void) {
    if (g_CdLocked != 0) {
        return 0;
    }
    if (memory_is_locked() != 0) {
        return 0;
    }
    if (g_CdFrameMode != 0) {
        VSyncCallback(0);
    }
    if (g_CdReadPhase == 1) {
        cd_file_driver_read_state1();
    } else if (g_CdReadPhase == 2) {
        cd_file_driver_read_state2();
    }
    if (g_CdCallbackActive != 0) {
        ((void (*)(void))((void **) cd_file_driver_get_vtable())[26])();
    }
    if (g_CdFrameMode != 0) {
        VSyncCallback(cd_file_driver_tick);
    }
    return 0;
}

void cd_file_driver_start_read(void) {
    cd_file_driver_lock();
    if (g_CdCallbackInstalled == 0) {
        if (g_CdFrameMode != 0) {
            VSyncCallback(cd_file_driver_tick);
        }
        g_CdCallbackInstalled = 1;
    }
    g_CdCallbackActive = 1;
    cd_file_driver_unlock();
}

void cd_file_driver_stop_read(void) {
    cd_file_driver_lock();
    if (g_CdReadPhase == 0) {
        if (g_CdCallbackInstalled != 0) {
            if (g_CdFrameMode != 0) {
                VSyncCallback(0);
            }
            g_CdCallbackInstalled = 0;
            g_CdCallbackActive = 0;
        }
    }
    cd_file_driver_unlock();
}

void cd_file_driver_clear_callback(void) {
    cd_file_driver_lock();
    g_CdCallbackActive = 0;
    cd_file_driver_unlock();
}

void cd_file_driver_queue_request(file_buf_t *arg0, s32 arg1, s32 arg2, s32 arg3, s32 arg4) {
    cd_file_request_t *node = cd_file_driver_alloc_request();

    node->m_Unk2 = arg2;
    node->m_Unk5 = arg3;
    node->m_FileBuf = (s32) arg0;
    node->m_Unk4 = arg1;
    node->m_Unk6 = arg4;
    arg0->m_Flags = 0;
    arg0->m_Unk7_2 = arg0->m_Unk7_2 + 1;
    cd_file_driver_start_read();
}

cd_file_request_t *cd_file_driver_alloc_request(void) {
    cd_file_request_t *node;
    cd_file_request_t *cur;

    cd_file_driver_lock();
    node = memory_allocate_mem(0x24);
    if (node != NULL) {
        node->m_Prev = NULL;
        node->m_Next = NULL;
        node->m_Cancel = 0;
        node->m_Unk1 = 0;
        if (g_CdRequestList != NULL) {
            cur = g_CdRequestList;
            if (cur->m_Next != NULL) {
                do {
                    cur = cur->m_Next;
                } while (cur->m_Next != NULL);
            }
            cur->m_Next = node;
            node->m_Prev = cur;
        } else {
            g_CdRequestList = node;
        }
    }
    cd_file_driver_unlock();
    return node;
}

void cd_file_driver_free_request(cd_file_request_t *node) {
    cd_file_driver_lock();
    if (node != NULL) {
        if (node->m_Prev != NULL) {
            node->m_Prev->m_Next = node->m_Next;
        } else {
            g_CdRequestList = node->m_Next;
        }
        if (node->m_Next != NULL) {
            node->m_Next->m_Prev = node->m_Prev;
        }
        memory_free_mem(node);
    }
    cd_file_driver_unlock();
}

s32 cd_file_driver_find_disc_record(s32 arg0) {
    s32 p = g_CdDiscTable;
    s32 i = 0;

    cd_file_driver_lock();
    while (1) {
        if (strstr((char *) p, (char *) arg0) != 0) {
            cd_file_driver_unlock();
            return p;
        }
        i++;
        p += 0x1C;
        if (i >= g_CdDiscCount) {
            return 0;
        }
    }
}

s32 cd_file_driver_find_disc_record_index(s32 arg0) {
    s32 p = g_CdDiscTable;
    s32 i = 0;

    cd_file_driver_lock();
    while (1) {
        if (strstr((char *) p, (char *) arg0) != 0) {
            break;
        }
        i++;
        if (i >= g_CdDiscCount) {
            return -1;
        }
        p += 0x1C;
    }
    cd_file_driver_unlock();
    return i;
}

s32 cd_file_driver_get_disc_record(s32 arg0) {
    s32 base = g_CdDiscTable;
    s32 result;

    cd_file_driver_lock();
    result = base + (arg0 * 0x1C);
    cd_file_driver_unlock();
    return result;
}

void cd_file_driver_read_state1(void) {
    s32 state;
    s32 status;
    s32 result;
    s32 timeout;

    cd_file_driver_lock();
    state = g_CdReadState;
    switch (state) {
    case 1:
        if (CdControlF(2, (u8 *)(g_CdReadPos + 0x14)) != 0) {
            result = 2;
            goto set_result;
        }
        break;
    case 2:
        status = CdSync(1, 0);
        if (status == 2) {
            cd_file_driver_end_read();
            goto done;
        }
        if (status < 3) {
            if (status == 0) goto check_timeout;
            goto done;
        }
        if (status != 5) goto done;
        result = 1;
        goto set_result;
check_timeout:
        timeout = g_CdTimeoutCounter + 1;
        g_CdTimeoutCounter = timeout;
        if (timeout >= 0x259) {
            result = 1;
            goto set_result;
        }
        break;
    case 7:
        if (func_80029274(g_CdReadDest, (void *)g_CdReadLba, 0x80) != 0) {
            result = 8;
            goto set_result;
        }
        break;
    case 8:
        status = CdReadSync(1, 0);
        if (status == -1) {
            CdFlush();
            result = 1;
            goto set_result;
        } else if (status == 0) {
            cd_file_driver_end_read();
        }
        break;
    }
    goto done;
set_result:
    cd_file_driver_set_read_result(result);
done:
    cd_file_driver_unlock();
}


void cd_file_driver_read_state2(void) {
    s32 state;
    s32 status;
    s32 result;
    s32 timeout;

    cd_file_driver_lock();
    state = g_CdReadState;
    switch (state) {
    case 1:
        if (CdControlF(2, (u8 *)(g_CdReadPos + 0x14)) != 0) {
            result = 2;
            goto set_result;
        }
        break;
    case 2:
        status = CdSync(1, 0);
        if (status == 2) {
            goto start_sector_read;
        }
        if (status < 3) {
            if (status == 0) goto check_timeout;
            goto done;
        }
        result = 1;
        if (status == 5) goto set_result;
        goto done;
start_sector_read:
        result = 7;
        goto set_result;
check_timeout:
        timeout = g_CdTimeoutCounter + 1;
        g_CdTimeoutCounter = timeout;
        if (timeout >= 0x259) {
            result = 1;
            goto set_result;
        }
        break;
    case 7:
        if (func_80029274(g_CdReadDest, (void *)g_CdReadLba, 0x80) != 0) {
            result = 8;
            goto set_result;
        }
        break;
    case 8:
        status = CdReadSync(1, 0);
        if (status == -1) {
            result = 1;
            goto set_result;
        } else if (status == 0) {
            cd_file_driver_end_read();
            g_CdReadPos = g_CdReadTarget;
            g_CdReadTarget = 0;
        }
        break;
    }
    goto done;
set_result:
    cd_file_driver_set_read_result(result);
done:
    cd_file_driver_unlock();
}

void cd_file_driver_begin_read(s32 arg0, s32 arg1) {
    g_CdReadBusy = 1;
    g_CdReadParam = arg0;
    g_CdReadState = arg1;
    g_CdReadIdle = 0;
    g_CdRequestList->m_Cancel = 1;
}

void cd_file_driver_end_read(void) {
    g_CdReadParam = 0;
    g_CdReadState = 0;
    g_CdReadPhase = 0;
    g_CdReadIdle = 1;
    g_CdTimeoutCounter = 0;
    g_CdReadBusy = 0;
}

void cd_file_driver_set_read_result(s32 arg0) {
    g_CdReadState = arg0;
    g_CdTimeoutCounter = 0;
}

void cd_file_driver_construct2(file_buf_t *This) {
    file_buf_get_vtable()->Construct(This);
    This->vtable = cd_file_driver_get_vtable();
    This->m_Unk2 = 0;
}

void cd_file_driver_cleanup2(file_buf_t *This) {
    file_buf_get_vtable()->Cleanup((base_class_t *) This);
}

void cd_file_driver_nullsub16(void) {
}

extern s32 printf(char *, ...);
extern char g_CdFileNotFoundPathFmt[];

void cd_file_driver_lookup_file(file_buf_t *This, s8 *arg1) {
    unk_disc_file_t file;
    s8 path[0x40];
    s32 count;
    if (This->m_Unk2 == 0) {
        count = 0;
        cd_file_driver_build_path(path, arg1);
retry:
        if (CdSearchFile(&file, (char *)path) == 0) {
            if (count++ < 0x64) {
                goto retry;
            }
            printf(g_CdFileNotFoundPathFmt, path);
            return;
        }
        *(unk_disc_loc_t *)((u8 *)This + 0x18) = file.m_Pos;
        This->m_Unk6 = file.m_Size;
        This->m_Unk2 = 1;
    }
}



s8 *cd_file_driver_build_path(s8 *arg0, s8 *arg1) {
    *arg0 = 0x5C;
    strcpy(arg0 + 1, (char *) get_current_data_folder());
    strcat(arg0, arg1);
    strcat(arg0, g_CdPathSuffix);
    return arg0;
}

void cd_file_driver_reset_cache(file_buf_t *This) {
    if (This->m_Unk2 != 0) {
        This->m_Unk2 = 0;
    }
}

s32 cd_file_driver_get_aligned_size(file_buf_t *This) {
    if (This->m_Unk2 != 0) {
        return (((u32) This->m_Unk6 >> 11) + 1) << 11;
    }
    return 0;
}

void cd_file_driver_nullsub17(void) {
}

/*
 * Reads `bytes` bytes of CD data into `destination` through the blocking
 * control/read polling path. The inherited unused `sector[0x800]` keeps the
 * target's 0x838 frame, but its original source purpose remains unexplained. It is
 * tracked in docs/UNUSED_LOCAL_CENSUS.md, not credited as explained storage.
 * The goto-based retry loop (both the sync==5 and read==-1 paths)
 * is required to keep `sectors = bytes >> 11` and the CdSync call setup inside
 * the loop instead of hoisting them.
 */
s32 cd_file_driver_read_sectors(file_buf_t *file, void *destination, u32 bytes) {
    u8 sector[0x800];
    s32 result[4];
    s32 status;
    u32 sectors;

    if (file->m_Unk2 != 0) {
    retry:
        sectors = bytes >> 11;
        CdControl(2, (u8 *) &file->m_Unk5, 0);
    syncloop:
        status = CdSync(0, (u8 *) result);
        if (status == 0) {
            goto syncloop;
        }
        if (status == 5) {
            goto retry;
        }
        if (sectors == 0) {
            goto done;
        }
        func_80029274(sectors, destination, 0x80);
        do {
            status = CdReadSync(0, 0);
        } while (status > 0);
        if (status == -1) {
            goto retry;
        }
    done:;
    } else {
        file->vtable->Close(file);
    }
    return 0;
}

void cd_file_driver_nullsub18(void) {
}

s32 cd_file_driver_get_frame_mode(void) {
    return g_CdFrameMode;
}
