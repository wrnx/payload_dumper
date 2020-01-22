#!/usr/bin/env python3

import argparse
import base64
import bz2
import hashlib
import os
import struct
import subprocess
import sys
import tempfile

try:
    import lzma
except ImportError:
    from backports import lzma

import update_metadata_pb2 as um


def u32(x):
    return struct.unpack('>I', x)[0]


def u64(x):
    return struct.unpack('>Q', x)[0]


def b64(x):
    return base64.b64encode(x).decode('utf-8')


def replace_operation(op, args, out_file):
    """ Replace the dst_extents on the drive with the attached data, zero padding out to block size """
    assert op.type == op.REPLACE or op.type == op.REPLACE_BZ or op.type == op.REPLACE_XZ

    data = args.payload_file.read(op.data_length)

    data_sha256_hash = hashlib.sha256()
    data_sha256_hash.update(data)
    assert data_sha256_hash.digest() == op.data_sha256_hash

    if op.type == op.REPLACE_BZ:
        data = bz2.BZ2Decompressor().decompress(data)
    elif op.type == op.REPLACE_XZ:
        data = lzma.LZMADecompressor().decompress(data)

    for dst_ext in op.dst_extents:
        out_file.seek(dst_ext.start_block * block_size)
        out_file.write(data)

        if (len(data) % block_size) > 0:
            out_file.write(bytes('\0', encoding='utf-8') * (block_size - (len(data) % block_size)))


def move_operation(op, args, out_file):
    """ Copy the data in src_extents to dst_extents. (deprecated) """
    assert op.type == op.MOVE

    data = bytes()

    for src_ext in op.src_extents:
        out_file.seek(src_ext.start_block * block_size)
        data += out_file.read(src_ext.num_blocks * block_size)

    data_sha256_hash = hashlib.sha256()
    data_sha256_hash.update(data)
    assert data_sha256_hash.digest() == op.src_sha256_hash

    for dst_ext in op.dst_extents:
        out_file.seek(dst_ext.start_block * block_size)
        out_file.write(data)


def bsdiff_operation(op, args, out_file): # TODO
    """
    Read src_length bytes from src_extents into memory, perform
    bspatch with attached data, write new data to dst_extents, zero padding
    to block size. (deprecated)
    """
    assert op.type == op.BSDIFF

    pass


def source_copy_operation(op, args, out_file):
    """
    Copy the data in src_extents in the old partition to
    dst_extents in the new partition
    """
    assert op.type == op.SOURCE_COPY

    data = bytes()

    with open('%s/%s.img' % (args.old_dir, partition.partition_name), 'rb') as old_file:
        for src_ext in op.src_extents:
            old_file.seek(src_ext.start_block * block_size)
            data += old_file.read(src_ext.num_blocks * block_size)

    data_sha256_hash = hashlib.sha256()
    data_sha256_hash.update(data)
    assert data_sha256_hash.digest() == op.src_sha256_hash

    for dst_ext in op.dst_extents:
        out_file.seek(dst_ext.start_block * block_size)
        out_file.write(data)


def source_diff_operation(op, args, out_file):
    """
    Read the data in src_extents in the old partition, perform
    bspatch or puffpatch with the attached data and write the new data to dst_extents in the
    new partition
    """
    assert op.type == op.SOURCE_BSDIFF or op.type == op.PUFFDIFF or op.type == op.BROTLI_BSDIFF

    old_filename = '%s/%s.img' % (args.old_dir, partition.partition_name)
    old_extents = ''
    new_extents = ''

    with open(old_filename, 'rb') as old_file:
        old_data_sha256_hash = hashlib.sha256()

        for src_ext in op.src_extents:
            old_extents += '%d:%d,' % (src_ext.start_block * block_size, src_ext.num_blocks * block_size)

            old_file.seek(src_ext.start_block * block_size)
            old_data = old_file.read(src_ext.num_blocks * block_size)
            old_data_sha256_hash.update(old_data)

        assert old_data_sha256_hash.digest() == op.src_sha256_hash

    with tempfile.NamedTemporaryFile('wb') as patch_file:
        patch_sha256_hash = hashlib.sha256()
        patch = args.payload_file.read(op.data_length)
        patch_sha256_hash.update(patch)
        assert patch_sha256_hash.digest() == op.data_sha256_hash
        patch_file.write(patch)
        patch_file.flush()
        assert os.stat(patch_file.name).st_size == op.data_length

        for dst_ext in op.dst_extents:
            new_extents += '%d:%d,' % (dst_ext.start_block * block_size, dst_ext.num_blocks * block_size)

        if op.type == op.PUFFDIFF:
            subprocess.run(['puffin', '-operation', 'puffpatch', '-src_file', old_filename, '-dst_file', out_file.name, '-patch_file', patch_file.name, '-src_extents', old_extents[:-1], '-dst_extents', new_extents[:-1]])
        else:
            subprocess.run(['bspatch', old_filename, out_file.name, patch_file.name, old_extents[:-1], new_extents[:-1]])


def zero_operation(op, args, out_file):
    """ Write zeros to the destination dst_extents """
    assert op.type == op.ZERO or op.type == op.DISCARD

    for dst_ext in op.dst_extents:
        out_file.seek(dst_ext.start_block * block_size)
        out_file.write(bytes('\0', encoding='utf-8') * (dst_ext.num_blocks * block_size))


def dump_partition(args, block_size, data_offset, partition):
    os.makedirs(args.out_dir, exist_ok=True)

    print(partition.partition_name)
    if args.verbose:
        print('    Hash (sha256): %s (size=%d)' % (b64(partition.new_partition_info.hash), partition.new_partition_info.size))

    with open('%s/%s.img' % (args.out_dir, partition.partition_name), 'wb') as out_file:
        try:
            for op in partition.operations:
                args.payload_file.seek(data_offset + op.data_offset)

                if args.verbose > 1:
                    print ('    Operation type=\'%s\', data_length=%d, data_sha256_hash=\'%s\', src_length=%d, src_sha256_hash=\'%s\'' %
                           (op.DESCRIPTOR.EnumValueName('Type', op.type), op.data_length, b64(op.data_sha256_hash), op.src_length, b64(op.src_sha256_hash)))

                if op.type == op.REPLACE:
                    replace_operation(op, args, out_file)
                elif op.type == op.REPLACE_BZ:
                    replace_operation(op, args, out_file)
                elif op.type == op.MOVE:
                    move_operation(op, args, out_file)
#                elif op.type == op.BSDIFF:
#                    bsdiff_operation(op, args, out_file)
                elif op.type == op.SOURCE_COPY:
                    source_copy_operation(op, args, out_file)
                elif op.type == op.SOURCE_BSDIFF:
                    source_diff_operation(op, args, out_file)
                elif op.type == op.ZERO:
                    zero_operation(op, args, out_file)
                elif op.type == op.DISCARD:
                    zero_operation(op, args, out_file)
                elif op.type == op.REPLACE_XZ:
                    replace_operation(op, args, out_file)
                elif op.type == op.PUFFDIFF:
                    source_diff_operation(op, args, out_file)
                elif op.type == op.BROTLI_BSDIFF:
                    source_diff_operation(op, args, out_file)
                else:
                    print('    Unsupported operation type: %s' % op.DESCRIPTOR.EnumValueName('Type', op.type), file=sys.stderr)
                    os.unlink(out_file.name)
                    return
        except FileNotFoundError as e:
            print('    E: %s: %s' % (e.strerror, e.filename), file=sys.stderr)
            os.unlink(out_file.name)
            return
        except AssertionError as e:
            print('    E: Assertion error: Make sure the files are in the correct version and are not corrupted!')
            os.unlink(out_file.name)
            return
        except:
            os.unlink(out_file.name)
            raise

    if args.check:
        BLOCK_SIZE = 1048576
        data_size = partition.new_partition_info.size

        with open('%s/%s.img' % (args.out_dir, partition.partition_name), 'rb') as image_file:
            partition_sha256_hash = hashlib.sha256()

            data = image_file.read(min(data_size, BLOCK_SIZE))
            data_size -= len(data)

            while len(data) > 0:
                partition_sha256_hash.update(data)
                data = image_file.read(min(data_size, BLOCK_SIZE))
                data_size -= len(data)

            if partition_sha256_hash.digest() != partition.new_partition_info.hash:
                print('    Hash mismatch (sha256): excepted="%s", actual="%s"' % (b64(partition.new_partition_info.hash), b64(partition_sha256_hash.digest())), file=sys.stderr)
            else:
                print('    Hash match (sha256): %s (size=%d)' % (b64(partition_sha256_hash.digest()), partition.new_partition_info.size))


            assert os.stat(image_file.name).st_size == partition.new_partition_info.size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OTA payload dumper')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='enable verbose output')
    parser.add_argument('--old', default='old', metavar='OLD_DIR', dest='old_dir', help='directory with original images (default: old)')
    parser.add_argument('--out', default='out', metavar='OUT_DIR', dest='out_dir', help='output directory (default: out)')
    parser.add_argument('--check', action='store_true', help='check output image')
    parser.add_argument('payload_file', metavar='payload.bin', type=argparse.FileType('rb'), help='file payload.bin')
    args = parser.parse_args()

    magic = args.payload_file.read(4)
    assert magic == b'CrAU'

    file_format_version = u64(args.payload_file.read(8))
    assert file_format_version == 2

    manifest_size = u64(args.payload_file.read(8))
    metadata_signature_size = u32(args.payload_file.read(4))

    manifest = args.payload_file.read(manifest_size)
    metadata_signature = args.payload_file.read(metadata_signature_size)

    dam = um.DeltaArchiveManifest()
    dam.ParseFromString(manifest)

    block_size = dam.block_size
    data_offset = args.payload_file.tell()

    for partition in dam.partitions:
        dump_partition(args, block_size, data_offset, partition)
