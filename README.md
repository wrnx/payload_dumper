# Payload Dumper
`usage: payload_dumper.py [-h] [-v] [--old OLD_DIR] [--out OUT_DIR] [--check] payload.bin`

## Dependencies
- [python3](https://docs.python.org/3/)
- [protobuf](https://pypi.org/project/protobuf/)
- [bsdiff](#bsdiff)
- [puffin](#puffin)

## External tools

### bsdiff
###### Source
- https://android.googlesource.com/platform/external/bsdiff/+/refs/tags/android-10.0.0_r25

###### Dependencies (OS: [Debian](https://www.debian.org/))
- libbrotli-dev
- libbz2-dev
- libdivsufsort-dev

###### Build
```shell
git submodule update --init
cd bsdiff 

make
sudo cp bsdiff bspatch /usr/local/bin/
sudo cp -r include/bsdiff /usr/local/include/bsdiff
sudo cp libbsdiff.so libbspatch.so /usr/local/lib/
sudo ldconfig
```

### puffin
###### Source
- https://android.googlesource.com/platform/external/puffin/+/refs/tags/android-10.0.0_r25

###### Dependencies (OS: [Debian](https://www.debian.org/))
- [bsdiff](#bsdiff)
- libgflags-dev
- libgoogle-glog-dev
- libgtest-dev
- libprotobuf-dev
- protobuf-compiler

###### Build
```shell
git submodule update --init
cd puffin

git apply ../puffin.patch

protoc -Isrc --cpp_out=src src/puffin.proto
make
sudo cp puffin_binary /usr/local/bin/puffin
```
