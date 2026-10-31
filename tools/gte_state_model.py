"""Independent integer model for the reviewed renderer GTE command subset.

Architectural register values, not native host addresses, define the oracle.
This models the pinned core's functional behavior, including its MVMVA far-color
quirk and fixed-point widths. PS1 CPU scheduling and hardware equivalence are
separate requirements.
"""
import struct


def unsigned(value):
    return value & 0xFFFFFFFF


def signed(value, bits=32):
    return (value & ((1 << bits)-1)) - ((value >> (bits-1) & 1) << bits)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command_word(code, shift=1, matrix=0, vector=0, translation=3, limit=0):
    require(all(type(v) is int for v in (code, shift, matrix, vector, translation, limit))
            and code in (1, 6, 0x10, 0x12, 0x13, 0x16, 0x1B, 0x2D, 0x2E, 0x30, 0x3F)
            and shift in (0, 1) and matrix in range(4) and vector in range(4)
            and translation in range(4) and limit in (0, 1), 'Unreviewed GTE command fields.')
    return 0x4A000000 | shift << 19 | matrix << 17 | vector << 15 | translation << 13 | limit << 10 | code


def matrix_registers(values):
    require(len(values) == 9 and all(type(v) is int and -32768 <= v <= 32767 for v in values),
            'Nine signed matrix halfwords are required.')
    return list(struct.unpack('<5I', struct.pack('<10h', *values, 0)))


class GteState:
    def __init__(self):
        self.data_writes, self.commands = 0, 0
        self.reset()

    def reset(self):
        self.cr, self.dr, self.flags = [0]*32, [0]*32, 0

    def write(self, kind, register, value):
        require(type(kind) is int and kind in (0, 1) and type(register) is int and 0 <= register < 32
                and type(value) is int and 0 <= value <= 0xFFFFFFFF, 'Invalid architectural register write.')
        if kind == 0:
            if register in (4, 12, 20, 26, 27, 29, 30):
                value &= 0xFFFF
            if register == 31:
                value = (value & 0x7FFFF000) | (0x80000000 if value & 0x7F87E000 else 0)
            self.cr[register] = value
            return
        self.data_writes += 1
        if register in (29, 31):
            return
        if register == 28:
            self.dr[9:12] = [((value >> (5*i)) & 31) << 7 for i in range(3)]
        elif register == 30:
            self.dr[30] = value
            self.dr[31] = 32 - (value ^ (0xFFFFFFFF if value & 0x80000000 else 0)).bit_length()
        elif register == 15:
            self.dr[12:16] = [self.dr[13], self.dr[14], value, value]
        elif register == 14:
            self.dr[14:16] = [value, value]
        elif register in (1, 3, 5, 8, 9, 10, 11):
            self.dr[register] = unsigned(signed(value, 16))
        elif register in (7, 16, 17, 18, 19):
            self.dr[register] = value & 0xFFFF
        else:
            self.dr[register] = value

    def control(self):
        return [unsigned(signed(value, 16)) if i in (4, 12, 20, 26, 27, 29, 30) else value
                for i, value in enumerate(self.cr)]

    def data(self):
        result = self.dr[:]
        packed = sum(min(31, max(0, signed(self.dr[9+i]) >> 7)) << (5*i) for i in range(3))
        result[28:30] = [packed, packed]
        return result

    def _limit(self, value, low, high, flag):
        if value < low or value > high:
            self.flags |= 1 << flag
        return min(high, max(low, value))

    def _accumulate(self, value, row):
        if value >= 1 << 43:
            self.flags |= 1 << (30-row)
        if value < -(1 << 43):
            self.flags |= 1 << (27-row)
        return signed(value, 44)

    def _mac0(self, value):
        if value > 0x7FFFFFFF:
            self.flags |= 1 << 16
        if value < -0x80000000:
            self.flags |= 1 << 15
        return signed(value)

    def _ir(self, value, row, limit):
        return self._limit(value, 0 if limit else -32768, 32767, 24-row)

    def _matrix(self, index):
        if index == 3:
            r = (self.dr[6] & 255) << 4
            return [-r, r, signed(self.dr[8], 16)] + [signed(self.cr[1], 16)]*3 + [signed(self.cr[2], 16)]*3
        words = self.cr[8*index:8*index+5]
        return list(struct.unpack('<10h', struct.pack('<5I', *words)))[:9]

    def _vector(self, index):
        if index == 3:
            return [signed(v, 16) for v in self.dr[9:12]]
        xy, z = self.dr[2*index:2*index+2]
        return [signed(xy, 16), signed(xy >> 16, 16), signed(z, 16)]

    def _multiply(self, matrix, vector, translation, shift, limit, far_quirk=False, projection=False):
        totals = []
        for row in range(3):
            value = translation[row] << 12
            for col in range(3):
                value = self._accumulate(value + matrix[3*row+col]*vector[col], row)
                if far_quirk and col == 0:
                    self._ir(signed(value >> shift), row, 0)
                    value = 0
            totals.append(value)
        mac = [signed(v >> shift) for v in totals]
        self.dr[25:28] = list(map(unsigned, mac))
        ir = [self._ir(v, i, limit) for i, v in enumerate(mac[:2])]
        if projection:
            # IR3's flag uses unshifted geometry depth; its value uses MAC3.
            ir.append(min(32767, max(0 if limit else -32768, mac[2])))
            if not -32768 <= (totals[2] >> 12) <= 32767:
                self.flags |= 1 << 22
            z = self._limit(totals[2] >> 12, 0, 65535, 18)
            self.dr[16:20] = self.dr[17:20] + [z]
        else:
            ir.append(self._ir(mac[2], 2, limit))
        self.dr[9:12] = list(map(unsigned, ir))

    @staticmethod
    def reciprocal(index):
        # A separately computed integer lookup, including the guarded last bin.
        return max(0, ((0x40000 // (min(index, 255)+0x100) + 1) // 2)-0x101)

    def _divide(self, numerator, denominator):
        if denominator*2 <= numerator:
            self.flags |= 1 << 17
            return 0x1FFFF
        shift = 16-denominator.bit_length()
        normal = denominator << shift
        table = self.reciprocal(((normal & 0x7FFF)+0x40) >> 7)
        seed = 0x101+table
        error = (0x80-normal*seed) >> 8
        estimate = (seed*(0x20000+error)+0x80) >> 8
        return min(0x1FFFF, ((numerator << shift)*estimate+0x8000) >> 16)

    def _project(self, vector, shift, limit, depth_cue):
        self._multiply(self._matrix(0), vector, list(map(signed, self.cr[5:8])), shift, limit, projection=True)
        quotient = self._divide(self.cr[26] & 0xFFFF, self.dr[19])
        xy = []
        for axis in range(2):
            value = signed(self.cr[24+axis]) + signed(self.dr[9+axis])*quotient
            self._mac0(value)
            mac0 = signed(value >> 16)
            self.dr[24] = unsigned(mac0)
            xy.append(self._limit(mac0, -1024, 1023, 14-axis))
        packed = (xy[0] & 0xFFFF) | (xy[1] & 0xFFFF) << 16
        self.dr[12:16] = [self.dr[13], self.dr[14], packed, packed]
        if depth_cue:
            value = signed(self.cr[28]) + signed(self.cr[27], 16)*quotient
            self.dr[24] = unsigned(self._mac0(value))
            self.dr[8] = self._limit(value >> 12, 0, 4096, 12)

    def _rgb(self):
        channels = [self._limit(signed(self.dr[25+i]) >> 4, 0, 255, 21-i) for i in range(3)]
        value = (self.dr[6] & 0xFF000000) | sum(c << (8*i) for i, c in enumerate(channels))
        self.dr[20:23] = self.dr[21:23]+[value]

    def _depth(self, shift, limit, multiply):
        mac, ir = [], list(map(signed, self.dr[9:12]))
        for i in range(3):
            color = ((self.dr[6] >> (8*i)) & 255) << 4
            base = color*ir[i] if multiply else color << 12
            difference = signed(self._accumulate((signed(self.cr[21+i]) << 12)-base, i) >> shift)
            delta = self._ir(difference, i, 0)
            value = self._accumulate(base + signed(self.dr[8], 16)*delta, i)
            mac.append(signed(value >> shift))
        self.dr[25:28] = list(map(unsigned, mac))
        self.dr[9:12] = [unsigned(self._ir(value, i, limit)) for i, value in enumerate(mac)]
        self._rgb()

    def execute(self, command):
        require(type(command) is int and 0 <= command <= 0xFFFFFFFF
                and command & 0xFE000000 == 0x4A000000, 'Invalid COP2 command word.')
        code, shift, limit = command & 63, 12 if command & 1 << 19 else 0, command >> 10 & 1
        require(code in (1, 6, 0x10, 0x12, 0x13, 0x16, 0x1B, 0x2D, 0x2E, 0x30, 0x3F), 'Unreviewed GTE opcode.')
        self.flags, self.commands = 0, self.commands+1
        if code == 0x12:
            matrix, vector, cv = command >> 17 & 3, command >> 15 & 3, command >> 13 & 3
            translation = [0]*3 if cv == 3 else list(map(signed, self.cr[8*cv+5:8*cv+8]))
            self._multiply(self._matrix(matrix), self._vector(vector), translation, shift, limit, far_quirk=cv == 2)
        elif code in (1, 0x30):
            vectors = [self._vector(i) for i in range(3 if code == 0x30 else 1)]
            for i, vector in enumerate(vectors):
                self._project(vector, shift, limit, i == len(vectors)-1)
        elif code == 6:
            points = [(signed(v, 16), signed(v >> 16, 16)) for v in self.dr[12:15]]
            area = sum(points[i][0]*(points[(i+1)%3][1]-points[(i+2)%3][1]) for i in range(3))
            self.dr[24] = unsigned(self._mac0(area))
        elif code in (0x2D, 0x2E):
            scale = signed(self.cr[29 if code == 0x2D else 30], 16)
            value = scale*sum(self.dr[17:20] if code == 0x2D else self.dr[16:20])
            self.dr[24] = unsigned(self._mac0(value))
            if self.flags & 0x18000:
                self.flags |= 1 << 18
                self.dr[7] = 0 if self.flags & 0x8000 else 65535
            else:
                self.dr[7] = self._limit(signed(self.dr[24]) >> 12, 0, 65535, 18)
        elif code == 0x10:
            self._depth(shift, limit, False)
        else:
            for index in range(3 if code in (0x16, 0x3F) else 1):
                self._multiply(self._matrix(1), self._vector(index), [0]*3, shift, limit)
                self._multiply(self._matrix(2), list(map(signed, self.dr[9:12])),
                               list(map(signed, self.cr[13:16])), shift, limit)
                if code in (0x13, 0x16):
                    self._depth(shift, limit, True)
                else:
                    mac = [signed((((self.dr[6] >> (8*i)) & 255) << 4)*signed(self.dr[9+i]) >> shift)
                           for i in range(3)]
                    self.dr[25:28] = list(map(unsigned, mac))
                    self.dr[9:12] = [unsigned(self._ir(value, i, limit)) for i, value in enumerate(mac)]
                    self._rgb()
        self.cr[31] = self.flags | (0x80000000 if self.flags & 0x7F87E000 else 0)
        return {1:14, 6:7, 0x10:7, 0x12:7, 0x13:18, 0x16:43, 0x1B:16,
                0x2D:4, 0x2E:4, 0x30:22, 0x3F:38}[code]

    def request(self, reset, writes, command=None):
        require(type(reset) is bool and type(writes) in (list, tuple) and len(writes) <= 1024,
                'Invalid bounded state request.')
        if reset:
            self.reset()
        for operation in writes:
            require(type(operation) in (list, tuple) and len(operation) == 3, 'Invalid register write tuple.')
            self.write(*operation)
        cycles = None if command is None else self.execute(command)
        return dict(cr=self.control(), dr=self.data(), command_cycles_minus_one=cycles,
                    native_data_writes=self.data_writes, native_commands=self.commands)
