#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Warcraft III AMAI 中文智能 AI —— 一键安装

把 scripts/ 下的 5 个 .ai 写入你的魔兽争霸3 游戏本体 MPQ：
    War3Patch.mpq  <- Scripts\\common.ai
    War3x.mpq      <- Scripts\\common.ai / human.ai / orc.ai / undead.ai / elf.ai

装完全局生效：任意对战地图里的电脑都会使用这套 AI，无需逐张改装。

用法：
    python install.py                          # 自动查找游戏目录
    python install.py --game " D:\\Games\\war3"  # 手动指定
    python install.py --dry-run                # 只检查不写入
    python install.py --uninstall              # 还原（同 uninstall.py）

要求：Python 3.6+，无需安装任何第三方库。
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))

try:
    import mpqpatch
except ImportError:
    print('找不到 tools/mpqpatch.py —— 请确认解压完整。')
    sys.exit(1)

SCRIPTS = os.path.join(HERE, 'scripts')
AI_FILES = ['common.ai', 'human.ai', 'orc.ai', 'undead.ai', 'elf.ai']

# 优先级：先读注册表，再猜常见路径
REG_PATHS = [
    (r'SOFTWARE\Blizzard Entertainment\Warcraft III', 'InstallPath'),
    (r'SOFTWARE\WOW6432Node\Blizzard Entertainment\Warcraft III', 'InstallPath'),
]
COMMON_PATHS = [
    r'C:\Program Files (x86)\Warcraft III',
    r'C:\Program Files\Warcraft III',
    r'D:\Games\Warcraft III',
    r'D:\GAMES\war3',
    r'E:\Games\Warcraft III',
]


def norm_path(p):
    """兼容 Git-Bash / MSYS 风格路径（/d/Games/... -> D:/Games/...）"""
    if not p:
        return p
    if len(p) > 2 and p[0] == '/' and p[2] == '/':
        return p[1].upper() + ':' + p[2:]
    return p


def find_game_dir():
    try:
        import winreg
        for sub, key in REG_PATHS:
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        p, _ = winreg.QueryValueEx(k, key)
                        if p and os.path.isdir(p):
                            return p
                except OSError:
                    pass
    except ImportError:
        pass
    for p in COMMON_PATHS:
        if os.path.isdir(p):
            return p
    return None


def check_game_dir(path):
    """返回 (ok, 说明)"""
    if not path or not os.path.isdir(path):
        return False, '目录不存在'
    exe = [f for f in os.listdir(path)
           if f.lower() in ('war3.exe', 'frozen throne.exe', 'warcraft iii.exe')]
    if not exe:
        return False, '这里似乎不是魔兽争霸3 目录（没找到游戏主程序）'
    for f in ('War3x.mpq', 'War3Patch.mpq'):
        if not os.path.isfile(os.path.join(path, f)):
            return False, '缺少 %s（版本可能不对，本项目需要 1.24~1.28）' % f
    return True, 'OK'


def read_scripts():
    out = {}
    for n in AI_FILES:
        p = os.path.join(SCRIPTS, n)
        if not os.path.isfile(p):
            print('缺少脚本文件: %s' % p)
            sys.exit(1)
        out[n] = open(p, 'rb').read()
    return out


def install(game, dry_run=False):
    scripts = read_scripts()
    targets = [
        ('War3Patch.mpq', ['common.ai']),
        ('War3x.mpq', AI_FILES),
    ]
    print('游戏目录: %s' % game)
    print('待写入脚本: %s' % ', '.join('%s(%.0fKB)' % (n, len(scripts[n]) / 1024) for n in AI_FILES))
    print()

    for mpq, names in targets:
        path = os.path.join(game, mpq)
        print('--- %s ---' % mpq)
        info = mpqpatch.inspect(path)
        print('  归档 %d bytes, hash_num=%d, blk_num=%d'
              % (info['size'], info['hash_num'], info['block_num']))
        if dry_run:
            print('  [dry-run] 跳过写入')
            continue
        try:
            p = mpqpatch.Patch(path, backup=True, log=lambda s: print('  ' + s))
            for n in names:
                p.replace('Scripts\\' + n, scripts[n])
            ok = p.commit()
            print('  %s' % ('写入并校验成功' if ok else '!! 校验失败'))
            if not ok:
                return False
        except Exception as e:
            print('  !! 失败: %s' % e)
            print('  如果文件被占用，请先完全退出游戏（包括战网客户端）再重试。')
            return False
        print()
    return True


def uninstall(game):
    print('游戏目录: %s' % game)
    done = 0
    for mpq in ('War3Patch.mpq', 'War3x.mpq'):
        bak = os.path.join(game, mpq + '.orig')
        dst = os.path.join(game, mpq)
        if os.path.isfile(bak):
            shutil.copy2(bak, dst)
            print('  已还原 %s（来自 %s.orig）' % (mpq, mpq))
            done += 1
        else:
            print('  跳过 %s：没有找到备份 %s.orig' % (mpq, mpq))
    if done:
        print('\n还原完成。电脑将回到暴雪原版 AI。')
        print('（备份文件保留着，可以重复还原）')
    else:
        print('\n没有可还原的备份。')
    return done > 0


def main():
    ap = argparse.ArgumentParser(description='Warcraft III AMAI 中文智能 AI 安装器')
    ap.add_argument('--game', help='魔兽争霸3 安装目录（含 War3x.mpq）')
    ap.add_argument('--dry-run', action='store_true', help='只检查，不写入')
    ap.add_argument('--uninstall', action='store_true', help='从备份还原')
    args = ap.parse_args()

    game = norm_path(args.game) or find_game_dir()
    if not game:
        print('没有自动找到魔兽争霸3 目录，请用 --game 指定，例如：')
        print('    python install.py --game "D:\\Games\\Warcraft III"')
        return 1

    ok, why = check_game_dir(game)
    if not ok:
        print('目录检查失败: %s' % why)
        print('指定的是: %s' % game)
        return 1

    if args.uninstall:
        return 0 if uninstall(game) else 1

    print('=' * 56)
    print(' Warcraft III · AMAI 中文智能 AI')
    print('=' * 56)
    if not install(game, args.dry_run):
        return 1
    if args.dry_run:
        print('干跑结束，未做任何修改。')
        return 0
    print('=' * 56)
    print(' 安装完成 ✓')
    print('=' * 56)
    print()
    print('进游戏就能用：单人游戏 → 自定义游戏 → 任意对战图')
    print('添加电脑，难度选【普通】或【困难】')
    print('  ⚠️ 不要选“简单” —— 简单难度暴雪会用自己的原版 AI，会覆盖掉本 AI')
    print()
    print('想还原：python install.py --uninstall')
    return 0


if __name__ == '__main__':
    sys.exit(main())
