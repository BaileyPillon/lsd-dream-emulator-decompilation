#include "dream/dream_sys.h"

/* Target-compiler assertions only; no game method or binary data is emitted. */
typedef char reset_pointer_width[(sizeof(void *) == 4) ? 1 : -1];
typedef char reset_object_extent[(sizeof(dream_sys_t) == 0x928) ? 1 : -1];
typedef char reset_save_extent[((u32)&((dream_sys_t *)0)->m_IsNewGame -
                                (u32)&((dream_sys_t *)0)->m_SaveDataMagic == 0x700) ? 1 : -1];
typedef char reset_nav_extent[(sizeof(((dream_sys_t *)0)->m_NavChallenges) == 30) ? 1 : -1];
typedef char reset_reserved_extent[(sizeof(((dream_sys_t *)0)->m_Reserved684) == 500) ? 1 : -1];
#define RESET_OFFSET(field, offset) \
    typedef char reset_offset_##field[((u32)&((dream_sys_t *)0)->field == offset) ? 1 : -1]
RESET_OFFSET(m_IsFlashbackSession, 0x068);
RESET_OFFSET(m_SaveDataMagic, 0x178);
RESET_OFFSET(m_Year, 0x17C);
RESET_OFFSET(m_DayOfYear, 0x180);
RESET_OFFSET(m_TotalUnlockScore, 0x184);
RESET_OFFSET(m_NavigationScore, 0x188);
RESET_OFFSET(m_InstanceScore, 0x18C);
RESET_OFFSET(m_MoodHistory, 0x190);
RESET_OFFSET(m_FlashbackCount, 0x46C);
RESET_OFFSET(m_Flashbacks, 0x470);
RESET_OFFSET(m_Reserved5D8, 0x5D8);
RESET_OFFSET(m_NavChallenges, 0x5E0);
RESET_OFFSET(m_NavChallengesPad, 0x5FE);
RESET_OFFSET(m_DynamicLinkCount, 0x600);
RESET_OFFSET(m_Reserved604, 0x604);
RESET_OFFSET(m_ScreenShakeEnabled, 0x678);
RESET_OFFSET(m_Reserved67C, 0x67C);
RESET_OFFSET(m_Reserved680, 0x680);
RESET_OFFSET(m_Reserved684, 0x684);
RESET_OFFSET(m_IsNewGame, 0x878);
RESET_OFFSET(m_StoredDay, 0x88C);
RESET_OFFSET(m_Flag, 0x924);
#undef RESET_OFFSET
