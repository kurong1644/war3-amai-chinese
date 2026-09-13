# -*- coding: utf-8 -*-
"""MPQ 补丁工具（自包含，无第三方依赖）。

只做一件事：**替换 MPQ 归档里已存在文件的內容**，不新增/删除条目
（因此完全不需要动哈希表，风险最小）。

写入格式与暴雪原文件保持一致：
    [扇区表] (n+1) 个 uint32，首项 = 4*(n+1)（含表自身长度），项为绝对偏移
    [扇区0][扇区1]...
        每个扇区 = 1 字节压缩类型(0x02 = zlib) + zlib 流

数据追加在归档末尾，原有数据一个字节都不动；
只更新 block table 里对应条目的 offset / csize / fsize。

公共接口：
    inspect(mpq_path)                          -> dict  结构摘要
    read_file(mpq_path, inner_name)            -> bytes
    Patch(mpq_path).replace(name, data).commit()
"""
import os
import struct
import zlib
import hashlib

MASK = 0xFFFFFFFF
ZLIB_TYPE = 0x02
FLAG_COMPRESS = 0x00000200      # zlib 压缩
FLAG_ENCRYPTED = 0x00010000     # 条目已加密（本工具不支持替换这类文件）
FLAG_SINGLE_UNIT = 0x01000000   # 整文件作为单块（注意不是 0x00010000！）
HASH_TABLE_KEY = 0x300


# --------------------------------------------------------------------------
# 密码表与哈希
# --------------------------------------------------------------------------
def _build_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i in range(0x100):
        for k in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            t2 = seed & 0xFFFF
            table[i + k * 0x100] = (t1 | t2) & MASK
    return table


T = _build_table()


def hash_string(s, hashtype):
    """hashtype: 0x000=表偏移 0x100=名字A 0x200=名字B 0x300=表解密key"""
    if isinstance(s, str):
        s = s.encode('utf-8', 'replace')
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for c in s:                     # bytes 迭代得到 int
        ch = (c - 32) if 0x61 <= c <= 0x7A else c    # ASCII 小写转大写
        seed1 = (T[hashtype + ch] ^ ((seed1 + seed2) & MASK)) & MASK
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & MASK
    return seed1


# --------------------------------------------------------------------------
# 块加解密（seed 都用「明文」递推；两者互为逆运算）
# --------------------------------------------------------------------------
def decrypt_block(words, key):
    if key == 0:
        return list(words)
    seed = 0xEEEEEEEE
    out = []
    for v in words:
        seed = (seed + T[0x400 + (key & 0xFF)]) & MASK
        ch = (v ^ ((key + seed) & MASK)) & MASK
        out.append(ch)
        old = key
        key = ((((~old & MASK) << 0x15) & MASK) + 0x11111111) & MASK
        key = (key | (old >> 0x0B)) & MASK
        seed = (ch + seed + (seed << 5) + 3) & MASK
    return out


def encrypt_block(words, key):
    if key == 0:
        return list(words)
    seed = 0xEEEEEEEE
    out = []
    for v in words:
        seed = (seed + T[0x400 + (key & 0xFF)]) & MASK
        out.append((v ^ ((key + seed) & MASK)) & MASK)
        old = key
        key = ((((~old & MASK) << 0x15) & MASK) + 0x11111111) & MASK
        key = (key | (old >> 0x0B)) & MASK
        seed = (v + seed + (seed << 5) + 3) & MASK
    return out


# --------------------------------------------------------------------------
# 扇区编解码
# --------------------------------------------------------------------------
def encode_sectors(data, sector_size):
    nsect = (len(data) + sector_size - 1) // sector_size or 1
    tsize = 4 * (nsect + 1)
    body = b''
    offs = [tsize]
    for i in range(nsect):
        chunk = data[i * sector_size:(i + 1) * sector_size]
        comp = zlib.compress(chunk, 9)
        if len(comp) + 1 >= len(chunk):
            raise RuntimeError('扇区 %d 压缩无收益，会产生与原格式不一致的存储，已中止' % i)
        body += bytes([ZLIB_TYPE]) + comp
        offs.append(tsize + len(body))
    return struct.pack('<%dI' % (nsect + 1), *offs) + body


def decode_sectors(raw, fsize, sector_size):
    nsect = (fsize + sector_size - 1) // sector_size or 1
    tbl = struct.unpack_from('<%dI' % (nsect + 1), raw, 0)
    parts = []
    for i in range(nsect):
        d = raw[tbl[i]:tbl[i + 1]]
        if d and d[0] == ZLIB_TYPE:
            parts.append(zlib.decompress(d[1:]))
        else:
            parts.append(d)
    return b''.join(parts)


# --------------------------------------------------------------------------
# MPQ 读取
# --------------------------------------------------------------------------
class _MPQ(object):
    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        head = self.f.read(32)
        if head[:4] != b'MPQ\x1a':
            raise ValueError('不是 MPQ 文件: %s' % path)
        self.size = os.path.getsize(path)
        self._hsz, self._asz, self._ver, self._bsz = struct.unpack_from('<IIHH', head, 4)
        self.hoff, self.boff, self.hn, self.bn = struct.unpack_from('<IIII', head, 16)
        self.sector = 512 << self._bsz      # MPQ 规范：扇区大小 = 512 << wBlockSize
        self._load_tables()

    def _load_tables(self):
        self.f.seek(self.hoff)
        raw = self.f.read(self.hn * 16)
        ht = decrypt_block(list(struct.unpack('<%dI' % (len(raw) // 4), raw)),
                           hash_string('(hash table)', HASH_TABLE_KEY))
        self.ht = ht
        self.f.seek(self.boff)
        raw = self.f.read(self.bn * 16)
        self.bt = decrypt_block(list(struct.unpack('<%dI' % (len(raw) // 4), raw)),
                                hash_string('(block table)', HASH_TABLE_KEY))

    def block_index(self, name):
        h = hash_string(name, 0x000)
        ha = hash_string(name, 0x100)
        hb = hash_string(name, 0x200)
        idx = h % self.hn
        # 哈希条目布局: [0]=NameA [1]=NameB [2]=Locale [3]=BlockIndex
        for probe in range(self.hn):
            i = (idx + probe) % self.hn
            bo = i * 4
            if self.ht[bo + 3] == 0xFFFFFFFF:
                return None                      # 空槽，文件不存在
            if self.ht[bo] == ha and self.ht[bo + 1] == hb:
                bi = self.ht[bo + 3]
                return bi if bi < self.bn else None
        return None

    def info(self, name):
        bi = self.block_index(name)
        if bi is None:
            return None
        o = bi * 4
        off, csize, fsize, flags = self.bt[o], self.bt[o + 1], self.bt[o + 2], self.bt[o + 3]
        return {'block': bi, 'offset': off, 'csize': csize, 'fsize': fsize, 'flags': flags}

    def raw(self, name):
        i = self.info(name)
        if not i:
            return None
        self.f.seek(i['offset'])
        return self.f.read(i['csize'])

    def content(self, name):
        i = self.info(name)
        if not i:
            return None
        raw = self.raw(name)
        if i['flags'] & FLAG_SINGLE_UNIT:
            return zlib.decompress(raw[1:]) if raw and raw[0] == ZLIB_TYPE else raw
        if i['flags'] & FLAG_COMPRESS:
            return decode_sectors(raw, i['fsize'], self.sector)
        return raw[:i['fsize']]

    def close(self):
        self.f.close()


# --------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------
def inspect(mpq_path):
    m = _MPQ(mpq_path)
    r = {'path': mpq_path, 'size': m.size, 'sector': m.sector,
         'hash_num': m.hn, 'block_num': m.bn}
    m.close()
    return r


def read_file(mpq_path, inner_name):
    m = _MPQ(mpq_path)
    data = m.content(inner_name)
    m.close()
    return data


class Patch(object):
    """对单个 MPQ 做「替换已存在文件」的补丁。

        p = Patch(path)
        p.replace('Scripts\\common.ai', data)
        p.commit()
    """

    def __init__(self, mpq_path, backup=True, log=print):
        self.path = mpq_path
        self.log = log
        self.backup = backup
        self.m = _MPQ(mpq_path)
        self.queue = []          # [(inner_name, data, block_index)]

    def replace(self, inner_name, data):
        i = self.m.info(inner_name)
        if i is None:
            raise KeyError('归档里没有 %s（本工具只替换已存在的文件）' % inner_name)
        if i['flags'] & FLAG_ENCRYPTED:
            raise ValueError('%s 是加密存储，本工具不支持（游戏 AI 脚本通常未加密）' % inner_name)
        if not (i['flags'] & FLAG_COMPRESS):
            raise ValueError('%s 不是 zlib 压缩存储（flags=0x%08X），格式不支持' % (inner_name, i['flags']))
        self.queue.append((inner_name, data, i['block'], i))
        return self

    # -- 校验 -------------------------------------------------------------
    def verify_in_memory(self):
        """编码自校验：每个待写入数据都能解回原样"""
        for name, data, bi, info in self.queue:
            if info['flags'] & FLAG_SINGLE_UNIT:
                comp = zlib.compress(data, 9)
                if comp != data and zlib.decompress(comp) != data:
                    raise RuntimeError('%s 单块编码自校验失败' % name)
            else:
                payload = encode_sectors(data, self.m.sector)
                if decode_sectors(payload, len(data), self.m.sector) != data:
                    raise RuntimeError('%s 扇区编码自校验失败' % name)
            self.log('    编码自校验 OK  %s (%d -> 压缩)' % (name, len(data)))

    def commit(self, dry_backup_name=None):
        self.verify_in_memory()
        self.m.close()

        if self.backup:
            bak = self.path + '.orig'
            if not os.path.exists(bak):
                self.log('    备份原文件 -> %s' % bak)
                import shutil
                shutil.copy2(self.path, bak)
            else:
                self.log('    备份已存在: %s' % bak)

        m = _MPQ(self.path)
        f = open(self.path, 'r+b')
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        pad = (-pos) % m.sector
        if pad:
            f.write(b'\x00' * pad)
            pos += pad

        written = []
        for name, data, bi, info in self.queue:
            if info['flags'] & FLAG_SINGLE_UNIT:
                payload = bytes([ZLIB_TYPE]) + zlib.compress(data, 9)
            else:
                payload = encode_sectors(data, m.sector)
            f.write(payload)
            o = bi * 4
            m.bt[o + 0] = pos
            m.bt[o + 1] = len(payload)
            m.bt[o + 2] = len(data)
            # flags 保持不变
            written.append((name, pos, len(payload), len(data)))
            pos += len(payload)
        f.flush()
        new_size = f.tell()

        enc = encrypt_block(m.bt, hash_string('(block table)', HASH_TABLE_KEY))
        f.seek(m.boff)
        f.write(struct.pack('<%dI' % len(enc), *enc))
        f.seek(8)
        f.write(struct.pack('<I', new_size))
        f.close()

        for name, off, csz, fsz in written:
            self.log('    已写入 %-24s @0x%X  %d bytes' % (name, off, fsz))

        # 回读校验
        m2 = _MPQ(self.path)
        ok = True
        for name, data, bi, info in self.queue:
            got = m2.content(name)
            if got is None or hashlib.md5(got).hexdigest() != hashlib.md5(data).hexdigest():
                self.log('    !! 回读校验失败: %s' % name)
                ok = False
            else:
                self.log('    回读校验 OK  %s' % name)
        m2.close()
        return ok
