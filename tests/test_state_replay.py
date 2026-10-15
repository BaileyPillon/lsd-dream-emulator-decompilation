"""Saved-state restoration must finish before the observer's first capture."""
from pathlib import Path
import ctypes
import ctypes.util
import os
import shutil
import subprocess
import tempfile
import unittest

from tools.capture_state_replay import compose_observer, RESTORE_PREFIX

LUA = shutil.which('lua5.4') or shutil.which('lua')
LUA_LIBRARY = os.environ.get('LSD_TEST_LUA_LIBRARY') or ctypes.util.find_library('lua5.4')


def run_lua(driver, script):
    if LUA:
        return subprocess.run([LUA, '-', str(script)], input=driver, capture_output=True)
    library = ctypes.CDLL(LUA_LIBRARY)
    library.luaL_newstate.argtypes, library.luaL_newstate.restype = [], ctypes.c_void_p
    library.luaL_openlibs.argtypes = [ctypes.c_void_p]
    library.lua_createtable.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    library.lua_pushstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.lua_rawseti.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]
    library.lua_setglobal.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    library.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    library.luaL_loadbufferx.restype = ctypes.c_int
    library.lua_pcallk.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ssize_t, ctypes.c_void_p]
    library.lua_pcallk.restype = ctypes.c_int
    library.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    library.lua_tolstring.restype = ctypes.c_char_p
    library.lua_close.argtypes = [ctypes.c_void_p]
    state = library.luaL_newstate()
    if not state:
        raise RuntimeError('Unable to create the optional Lua interpreter.')
    try:
        library.luaL_openlibs(state)
        library.lua_createtable(state, 1, 0)
        library.lua_pushstring(state, str(script).encode('utf-8'))
        library.lua_rawseti(state, -2, 1)
        library.lua_setglobal(state, b'arg')
        code = library.luaL_loadbufferx(state, driver, len(driver), b'replay-order-test', b't')
        if code == 0:
            code = library.lua_pcallk(state, 0, 0, 0, 0, None)
        error = library.lua_tolstring(state, -1, None) if code else b''
        return subprocess.CompletedProcess(['optional-lua-library'], code, b'', error or b'')
    finally:
        library.lua_close(state)


class StateReplayTests(unittest.TestCase):
    def test_original_observer_bytes_are_retained(self):
        body = b'-- original observer\r\nlocal captured = true\r\n'
        self.assertEqual(compose_observer(body), RESTORE_PREFIX + body)

    def test_invalid_appended_source_is_rejected(self):
        for source in (b'', b' \n', b'\xef\xbb\xbflocal a = 1', b'\xff', 'text'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                compose_observer(source)

    @unittest.skipUnless(LUA or LUA_LIBRARY, 'Optional Lua interpreter is unavailable.')
    def test_actual_lua_restores_before_first_capture_and_detects_old_order(self):
        body = b'assert(memory == "saved memory" and frame == 12000)\ncaptures = captures + 1\n'
        driver = b'''local function environment()
    local env = {assert=assert, memory="startup memory", frame=0, captures=0}
    env.os = {getenv=function(name) assert(name=="LSD_QA_OUTPUT"); return "qa fixture" end}
    env.emu = {getsystemid=function() return "PSX" end}
    env.savestate = {load=function(path)
        assert(path=="qa fixture/start.State")
        env.memory="saved memory"; env.frame=12000
    end}
    return env
end
local file=assert(io.open(arg[1],"rb")); local source=file:read("*a"); file:close()
local env=environment(); assert(load(source,"production-wrapper","t",env))()
assert(env.captures==1 and env.frame==12000)
local old=environment()
assert(not pcall(assert(load('assert(memory=="saved memory" and frame==12000)',"old-order","t",old))))
assert(old.captures==0)
'''
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'replay.lua'
            script.write_bytes(compose_observer(body))
            result = run_lua(driver, script)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    @unittest.skipUnless(LUA or LUA_LIBRARY, 'Optional Lua interpreter is unavailable.')
    def test_failed_state_restore_never_runs_observer(self):
        driver = b'''local env={assert=assert,captures=0,os={getenv=function() return "qa" end},
    emu={getsystemid=function() return "PSX" end},savestate={load=function() error("restore failed") end}}
local file=assert(io.open(arg[1],"rb")); local source=file:read("*a"); file:close()
local ok,message=pcall(assert(load(source,"production-wrapper","t",env)))
assert(not ok and tostring(message):find("restore failed",1,true))
assert(env.captures==0)
'''
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'replay.lua'
            script.write_bytes(compose_observer(b'captures = captures + 1\n'))
            result = run_lua(driver, script)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
