import errno
import sys
import time
import argparse
from collections import namedtuple
from stat import S_IFDIR
from yggdrasil.diskspec import *

import cython
if not cython.compiled:
    from diskimpl import Allocator, DentryLookup
    from waldisk import WALDisk
    from disk import *
    from bitmap import BitmapDisk
    from inodepack import InodePackDisk
    from dirinode import DirImpl


__all__ = ['InodeDisk', 'IndirectInodeDisk']


#Disk = namedtuple('Disk', ['read', 'write'])

class Disk(object):
    def __init__(self, dev, _txndisk):
        #super(Disk, self).__init__()
        self.dev = dev
        self._txndisk = _txndisk

    def read(self, bid):
        return self._txndisk.read(self.dev, bid)

    def write(self, bid, data):
        self._txndisk.write_tx(self.dev, bid, data)

# note: this class is auto-generated
class InodeDisk:
    FREEDISK = None
    INODEMETADISK = None
    INODEDATADISK = None
    DATADISK = None
    NDIRECT = None

    def __init__(self, txndisk):
        self._INODEDATADISK = InodeDisk.INODEDATADISK
        self._NDIRECT = InodeDisk.NDIRECT
        self._txndisk = txndisk
        self._allocator = Allocator64(self._txndisk, InodeDisk.FREEDISK, 0, 1024)
        freedisk = Disk(InodeDisk.FREEDISK, self._txndisk)
        inodemeta = Disk(InodeDisk.INODEMETADISK, self._txndisk)
        inodedata = Disk(InodeDisk.INODEDATADISK, self._txndisk)
        self._bitmap = Bitmap(freedisk)
        self._inode = InodePack(inodemeta, inodedata)

    def begin_tx(self):
        self._txndisk.begin_tx()

    def commit_tx(self):
        self._txndisk.commit_tx()

    def get_iattr(self, ino):
        return self._inode.get_iattr(ino)

    def set_iattr(self, ino, attr):
        self._inode.set_iattr(ino, attr)

    def read(self, lbn):
        return self._txndisk.read(InodeDisk.DATADISK, lbn)

    def write_tx(self, lbn, data):
        self._txndisk.write_tx(InodeDisk.DATADISK, lbn, data)

    def write(self, lbn, data):
        self._txndisk.write_tx(InodeDisk.DATADISK, lbn, data)

    def mappingi(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        return If(ULT(off, self._NDIRECT), self._inode.get_mapping(ino, eoff), 0)

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return Not(self._bitmap.is_set(lbn))

    def alloc(self):
        lbn = self._allocator.alloc()
        assertion(lbn != 0)
        assertion(self.is_free(lbn))
        self._bitmap.set_bit(lbn)
        return lbn

    def free(self, lbn):
        return self._bitmap.unset_bit(lbn)

    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        iblock = self._inode.read(ino)
        old_lbn = self._inode.get_mapping(ino, eoff, iblock)
        valid = And(old_lbn == 0, ULT(off, self._NDIRECT))
        if valid:
            lbn = self.alloc()
            self.write_tx(lbn, ConstBlock(0))
            self._inode.set_mapping(ino, eoff, lbn, iblock)
            return lbn
        if ULT(off, self._NDIRECT):
            return old_lbn
        return 0

    def bunmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        if Not(ULT(off, self._NDIRECT)):
            return
        iblock = self._inode.read(ino)
        lbn = self._inode.get_mapping(ino, eoff, iblock)
        if lbn != 0:
            self.free(lbn)
            self._inode.set_mapping(ino, eoff, 0, iblock)

    def mkfs(self):
        self._bitmap.mkfs()
        self._inode.mkfs()

    def crash(self, mach):
        return self.__class__(self._txndisk.crash(mach))

InodeDisk.FREEDISK = 0

InodeDisk.INODEMETADISK = 1

InodeDisk.INODEDATADISK = 2

InodeDisk.DATADISK = 3

InodeDisk.NDIRECT = 11

'''
class InodeDisk(object):
    FREEDISK = 0
    INODEMETADISK = 1
    INODEDATADISK = 2
    DATADISK = 3

    # Number of direct blocks
    NDIRECT = 11

    def __init__(self, txndisk):
        self._INODEDATADISK = InodeDisk.INODEDATADISK
        self._NDIRECT = InodeDisk.NDIRECT

        self._txndisk = txndisk

        """
        self._Bitmap = Bitmap
        self._Allocator = Allocator64
        self._Inode = InodePack
        """

        """
        # Allocator is not verified
        self._allocator = Allocator64(
                lambda n: self._txndisk.read(self.FREEDISK, n),
                0, 1024)
        """
        self._allocator = Allocator64(self._txndisk, self.FREEDISK, 0, 1024)

        
        """
        freedisk = Disk(write=lambda bid, data: self._txndisk.write_tx(self.FREEDISK, bid, data),
                        read=lambda bid: self._txndisk.read(self.FREEDISK, bid))

        inodemeta = Disk(write=lambda bid, data: self._txndisk.write_tx(self.INODEMETADISK, bid, data),
                         read=lambda bid: self._txndisk.read(self.INODEMETADISK, bid))

        inodedata = Disk(write=lambda bid, data: self._txndisk.write_tx(self._INODEDATADISK, bid, data),
                         read=lambda bid: self._txndisk.read(self._INODEDATADISK, bid))
        """

        freedisk = Disk(self.FREEDISK, self._txndisk)
        inodemeta = Disk(self.INODEMETADISK, self._txndisk)
        inodedata = Disk(self.INODEDATADISK, self._txndisk)

        self._bitmap = Bitmap(freedisk)
        self._inode = InodePack(inodemeta, inodedata)

    FREEDISK = None
    INODEMETADISK = None
    INODEDATADISK = None
    DATADISK = None
    NDIRECT = None

    # auto-generated
    def __init__(self, txndisk):
        self._INODEDATADISK = InodeDisk.INODEDATADISK
        self._NDIRECT = InodeDisk.NDIRECT
        self._txndisk = txndisk
        self._allocator = Allocator64(self._txndisk, InodeDisk.FREEDISK, 0, 1024)
        freedisk = Disk(InodeDisk.FREEDISK, self._txndisk)
        inodemeta = Disk(InodeDisk.INODEMETADISK, self._txndisk)
        inodedata = Disk(InodeDisk.INODEDATADISK, self._txndisk)
        self._bitmap = Bitmap(freedisk)
        self._inode = InodePack(inodemeta, inodedata)


    def set_iattr(self, ino, attr):
        self._inode.set_iattr(ino, attr)

    def get_iattr(self, ino):
        return self._inode.get_iattr(ino)

    def begin_tx(self):
        self._txndisk.begin_tx()

    def commit_tx(self):
        self._txndisk.commit_tx()

    def read(self, lbn):
        return self._txndisk.read(self.DATADISK, lbn)

    def write_tx(self, lbn, data):
        self._txndisk.write_tx(self.DATADISK, lbn, data)

    def write(self, lbn, data):
        self._txndisk.write_tx(self.DATADISK, lbn, data)

    # ============start=============
    def begin_tx(self):
        self._txndisk.begin_tx()

    def commit_tx(self):
        self._txndisk.commit_tx()

    def get_iattr(self, ino):
        return self._inode.get_iattr(ino)

    def set_iattr(self, ino, attr):
        self._inode.set_iattr(ino, attr)

    def read(self, lbn):
        return self._txndisk.read(InodeDisk.DATADISK, lbn)

    def write_tx(self, lbn, data):
        self._txndisk.write_tx(InodeDisk.DATADISK, lbn, data)

    def write(self, lbn, data):
        self._txndisk.write_tx(InodeDisk.DATADISK, lbn, data)

    def mappingi(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        return If(ULT(off, self._NDIRECT), self._inode.get_mapping(ino, eoff), 0)

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return Not(self._bitmap.is_set(lbn))

    def alloc(self):
        lbn = self._allocator.alloc()
        assertion(lbn != 0)
        assertion(self.is_free(lbn))
        self._bitmap.set_bit(lbn)
        return lbn

    def free(self, lbn):
        return self._bitmap.unset_bit(lbn)

    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        iblock = self._inode.read(ino)
        old_lbn = self._inode.get_mapping(ino, eoff, iblock)
        valid = And(old_lbn == 0, ULT(off, self._NDIRECT))
        if valid:
            lbn = self.alloc()
            self.write_tx(lbn, ConstBlock(0))
            self._inode.set_mapping(ino, eoff, lbn, iblock)
            return lbn
        if ULT(off, self._NDIRECT):
            return old_lbn
        return 0

    # =============end==============

    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(eoff='unsigned long long')
    def mappingi(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        # ino = cython.type('unsigned long long')
        # assertion ino.size() / 8 == sizeof(unsigned long long)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)
        return If(ULT(off, self._NDIRECT),
                self._inode.get_mapping(ino, eoff), 0)

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return Not(self._bitmap.is_set(lbn))

    @cython.locals(lbn='unsigned long long')
    def alloc(self):
        # black box allocator returns a vbn
        lbn = self._allocator.alloc()
        # Validation
        assertion(lbn != 0, "inode.alloc: lbn is 0")
        assertion(self.is_free(lbn), "inode alloc: lbn not free")
        self._bitmap.set_bit(lbn)
        return lbn

    def free(self, lbn):
        self._bitmap.unset_bit(lbn)

    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(eoff='unsigned long long')
    @cython.locals(iblock='Block')
    @cython.locals(old_lbn='unsigned long long')
    @cython.locals(valid='bint')
    @cython.locals(lbn='unsigned long long')
    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)

        iblock = self._inode.read(ino)

        old_lbn = self._inode.get_mapping(ino, eoff, block=iblock)

        valid = And(old_lbn == 0, ULT(off, self._NDIRECT))

        if valid:
            lbn = self.alloc()

            # Data write
            self.write_tx(lbn, ConstBlock(0))

            self._inode.set_mapping(ino, eoff, lbn, block=iblock)

            return lbn

        if ULT(off, self._NDIRECT):
            return old_lbn
        return 0

    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(eoff='unsigned long long')
    @cython.locals(iblock='Block')
    @cython.locals(lbn='unsigned long long')
    def bunmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, vbn)

        if Not(ULT(off, self._NDIRECT)):
            return

        iblock = self._inode.read(ino)

        lbn = self._inode.get_mapping(ino, eoff, block=iblock)

        if lbn != 0:
            self.free(lbn)
            self._inode.set_mapping(ino, eoff, 0, block=iblock)

    def crash(self, mach):
        """
        return self.__class__(self._txndisk.crash(mach),
                              self._Allocator,
                              self._Bitmap,
                              self._Inode)
        """
        return self.__class__(self._txndisk.crash(mach))

    def mkfs(self):
        self._bitmap.mkfs()
        self._inode.mkfs()
'''

'''
class IndirectInodeDisk(object):
    # ==========begin============
    NINDIRECT = None

    def __init__(self, idisk):
        self._NINDIRECT = IndirectInodeDisk.NINDIRECT
        self._idisk = idisk

    def begin_tx(self):
        self._idisk.begin_tx()

    def commit_tx(self):
        self._idisk.commit_tx()

    def get_iattr(self, ino):
        return self._idisk.get_iattr(ino)

    def set_iattr(self, ino, attr):
        self._idisk.set_iattr(ino, attr)

    def read(self, lbn):
        return self._idisk.read(lbn)

    def write_tx(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def write(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def mappingi(self, vbn):
        ndir = self._idisk._NDIRECT
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        is_direct = ULT(off, ndir)
        off = USub(off, ndir)
        vbnm = Concat32(ino, BitVecVal(ndir - 1, 32))
        ind_mapped = self._idisk.is_mapped(vbnm)
        ind_mapping = self._idisk.mappingi(vbnm)
        ind_block = self._idisk.read(ind_mapping)
        return If(is_direct, self._idisk.mappingi(vbn), If(And(ULT(off, self._NINDIRECT), ind_mapped), ind_block.get(Extract(8, 0, off)), 0))

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return self._idisk.is_free(lbn)

    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(off, self._idisk._NDIRECT))
        if ULT(off, self._idisk._NDIRECT):
            return self._idisk.bmap(vbn)
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return 0
        mapping = self._idisk.bmap(Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))
        imap = self._idisk.read(mapping)
        old_lbn = imap.__getitem__(eoff)
        if old_lbn == 0:
            lbn = self._idisk.alloc()
            self.write_tx(lbn, ConstBlock(0))
            imap.__setitem__(eoff, lbn)
            self.write_tx(mapping, imap)
            return lbn
        return old_lbn

    def bunmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(vbn, self._idisk._NDIRECT))
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return
        if ULT(off, self._idisk._NDIRECT):
            self._idisk.bunmap(vbn)
            return
        mapping = self._idisk.mappingi(Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))
        imap = self._idisk.read(mapping)
        if Or(mapping == 0, imap.__getitem__(eoff) == 0):
            return
        lbn = imap.__getitem__(eoff)
        imap.__setitem__(eoff, 0)
        self._idisk.free(lbn)
        self.write_tx(mapping, imap)

    # ===========end=============

    NINDIRECT = 512

    def __init__(self, idisk):
        self._NINDIRECT = IndirectInodeDisk.NINDIRECT
        self._idisk = idisk

    def get_iattr(self, ino):
        return self._idisk.get_iattr(ino)

    def set_iattr(self, ino, attr):
        self._idisk.set_iattr(ino, attr)

    def read(self, lbn):
        return self._idisk.read(lbn)

    def write_tx(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def write(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def begin_tx(self):
        self._idisk.begin_tx()

    def commit_tx(self):
        self._idisk.commit_tx()

    @cython.locals(ndir='unsigned long long')
    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(is_direct='bint')
    @cython.locals(off='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(vbnm='unsigned long long')
    @cython.locals(ind_mapped='bint')
    @cython.locals(ind_mapping='unsigned long long')
    @cython.locals(ind_block='Block')
    def mappingi(self, vbn):
        ndir = self._idisk._NDIRECT

        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)

        is_direct = ULT(off, ndir)

        off = USub(off, ndir)

        vbnm = Concat32(ino, BitVecVal(ndir - 1, 32))

        ind_mapped = self._idisk.is_mapped(vbnm)
        ind_mapping = self._idisk.mappingi(vbnm)
        ind_block = self._idisk.read(ind_mapping)

        return If(is_direct, self._idisk.mappingi(vbn), If(And(ULT(off, self._NINDIRECT), ind_mapped), ind_block.get(Extract(8, 0, off)), 0))

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return self._idisk.is_free(lbn)

    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(eoff='unsigned long long')
    @cython.locals(mapping='unsigned long long')
    @cython.locals(imap='Block')
    @cython.locals(old_lbn='unsigned long long')
    @cython.locals(lbn='unsigned long long')
    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(off, self._idisk._NDIRECT))

        # Off is direct
        if ULT(off, self._idisk._NDIRECT):
            return self._idisk.bmap(vbn)

        # Off is not within bounds
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return 0

        mapping = self._idisk.bmap(
                Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))

        imap = self._idisk.read(mapping)

        old_lbn = imap.__getitem__(eoff)

        # Off is not-mapped
        if old_lbn == 0:

            lbn = self._idisk.alloc()

            self.write_tx(lbn, ConstBlock(0))

            #imap[eoff] = lbn
            imap.__setitem__(eoff, lbn)
            self.write_tx(mapping, imap)

            return lbn
        return old_lbn


    @cython.locals(ino='unsigned long long')
    @cython.locals(off='unsigned long long')
    @cython.locals(eoff='unsigned long long')
    @cython.locals(mapping='unsigned long long')
    @cython.locals(imap='Block')
    @cython.locals(lbn='unsigned long long')
    def bunmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(vbn, self._idisk._NDIRECT))

        # Off is out of bounds
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return

        # Off is direct
        if ULT(off, self._idisk._NDIRECT):
            self._idisk.bunmap(vbn)
            return

        mapping = self._idisk.mappingi(
                Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))

        imap = self._idisk.read(mapping)

        # Off is not mapped
        if Or(mapping == 0, imap.__getitem__(eoff) == 0):
            return

        #lbn = imap[eoff]
        lbn = imap.__getitem__(eoff)

        #imap[eoff] = 0
        imap.__setitem__(eoff, 0)

        self._idisk.free(lbn)
        self.write_tx(mapping, imap)


    def crash(self, mach):
        return self.__class__(self._idisk.crash(mach))

IndirectInodeDisk.NINDIRECT = 512
'''

# note: this class is auto-generated
class IndirectInodeDisk:
    NINDIRECT = None

    def __init__(self, idisk):
        self._NINDIRECT = IndirectInodeDisk.NINDIRECT
        self._idisk = idisk

    def begin_tx(self):
        self._idisk.begin_tx()

    def commit_tx(self):
        self._idisk.commit_tx()

    def get_iattr(self, ino):
        return self._idisk.get_iattr(ino)

    def set_iattr(self, ino, attr):
        self._idisk.set_iattr(ino, attr)

    def read(self, lbn):
        return self._idisk.read(lbn)

    def write_tx(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def write(self, lbn, data):
        self._idisk.write_tx(lbn, data)

    def mappingi(self, vbn):
        ndir = self._idisk._NDIRECT
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        is_direct = ULT(off, ndir)
        off = USub(off, ndir)
        vbnm = Concat32(ino, BitVecVal(ndir - 1, 32))
        ind_mapped = self._idisk.is_mapped(vbnm)
        ind_mapping = self._idisk.mappingi(vbnm)
        ind_block = self._idisk.read(ind_mapping)
        return If(is_direct, self._idisk.mappingi(vbn), If(And(ULT(off, self._NINDIRECT), ind_mapped), ind_block.get(Extract(8, 0, off)), 0))

    def is_mapped(self, vbn):
        return self.mappingi(vbn) != 0

    def is_free(self, lbn):
        return self._idisk.is_free(lbn)

    def bmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(off, self._idisk._NDIRECT))
        if ULT(off, self._idisk._NDIRECT):
            return self._idisk.bmap(vbn)
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return 0
        mapping = self._idisk.bmap(Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))
        imap = self._idisk.read(mapping)
        old_lbn = imap.__getitem__(eoff)
        if old_lbn == 0:
            lbn = self._idisk.alloc()
            self.write_tx(lbn, ConstBlock(0))
            imap.__setitem__(eoff, lbn)
            self.write_tx(mapping, imap)
            return lbn
        return old_lbn

    def bunmap(self, vbn):
        ino = Extract(64 - 1, 32, vbn)
        off = Extract(32 - 1, 0, vbn)
        eoff = Extract(9 - 1, 0, USub(vbn, self._idisk._NDIRECT))
        if Not(ULT(off, self._idisk._NDIRECT + self._NINDIRECT)):
            return
        if ULT(off, self._idisk._NDIRECT):
            self._idisk.bunmap(vbn)
            return
        mapping = self._idisk.mappingi(Concat32(ino, BitVecVal(self._idisk._NDIRECT - 1, 32)))
        imap = self._idisk.read(mapping)
        if Or(mapping == 0, imap.__getitem__(eoff) == 0):
            return
        lbn = imap.__getitem__(eoff)
        imap.__setitem__(eoff, 0)
        self._idisk.free(lbn)
        self.write_tx(mapping, imap)

    def crash(self, mach):
        return self.__class__(self._idisk.crash(mach))

IndirectInodeDisk.NINDIRECT = 512

'''
@cython.locals(fdisk='DirImpl')
@cython.locals(inode='IndirectInodeDisk')
@cython.locals(root_attr='Stat')
def mkfs(fdisk):
    inode = fdisk._inode

    inode.begin_tx()

    attr = inode.get_iattr(1)

    if attr.nlink == 0:
        # Initialize the root directory
        attr.mode = 0755 | S_IFDIR
        attr.mtime = int(time.time())
        attr.nlink = 2

        inode.set_iattr(1, attr)

        # Reserve datablock 0
        inode._idisk._bitmap.set_bit(0)

        # Reserve inodes 0 and 1
        fdisk._ibitmap.set_bit(0)
        fdisk._ibitmap.set_bit(1)

        fdisk._txndisk.commit_tx(True)


_curr = 0
def create_partition(disk, size, debug=False):
    global _curr
    start = _curr
    _curr += size
    end = start + size
    print "Creating partition:", start, end
    return PartitionAsyncDisk(disk, start, end, debug)


def create_fuse_inode(args):
    print args
    parser = argparse.ArgumentParser(description='Yxv6')

    parser.add_argument('imgpath', metavar='PATH', type=str, help='Path to fs image')
    parser.add_argument('--isize', metavar='NUM', default=1, type=int, help='Number of inode blocks (multiple of 32k)')
    parser.add_argument('--dsize', metavar='NUM', default=1, type=int, help='Number data blocks (multiple of 32k)')
    parser.add_argument('--sync', help='Synchronous mode', action='store_true')
    parser.set_defaults(sync=False)

    args = parser.parse_args(args)

    print "args.imgpath = ", args.imgpath
    disk = AsyncDisk(args.imgpath)

    isize = args.isize
    dsize = args.dsize

    print ">>", args.imgpath
    print ">> number of inodes = %d" % (2 ** 15 * isize)
    print ">> fs size = %d MB" % (2 ** 15 * dsize * 4096 / 2 ** 20)
    print ">> sync = %r" % args.sync

    ifreedisk = create_partition(disk, isize)
    freedisk = create_partition(disk, dsize)
    inodedisk = create_partition(disk, 2 ** 15 * isize / 32)
    datadisk = create_partition(disk, 2 ** 15 * dsize)
    logdisk = create_partition(disk, 1027)
    orphandisk = create_partition(disk, 1)

    print "************ I am here"
    txndisk = WALDisk(logdisk, [freedisk, inodedisk, inodedisk, datadisk, ifreedisk, orphandisk], osync=args.sync)
    idisk = InodeDisk(txndisk, Allocator, BitmapDisk, InodePackDisk)
    idisk._INODEDATADISK = idisk.INODEMETADISK
    idisk = IndirectInodeDisk(idisk)

    fdisk = DirImpl(txndisk, idisk, Allocator, BitmapDisk, DentryLookup)
    mkfs(fdisk)

    return fdisk

'''
