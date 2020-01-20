# Payload Dumper

## Dependencies
- python3
- protobuf
- [bsdiff](#bsdiff)
- [puffin](#puffin)

## External tools

### bsdiff
###### Source
https://android.googlesource.com/platform/external/bsdiff/+archive/79d0acf62e249d4d3b38cd41e5b47bdee336145a.tar.gz

###### Dependencies
- libbrotli-dev
- libbz2-dev
- libdivsufsort-dev

###### Build
```shell
make
sudo cp bsdiff bspatch /usr/local/bin/
sudo cp -r include/bsdiff /usr/local/include/bsdiff
sudo cp libbsdiff.so libbspatch.so /usr/local/lib/
sudo ldconfig
```

### puffin
###### Source
https://android.googlesource.com/platform/external/puffin/+archive/bc7745523aef2d7f620ca16aa6ab11a8e38dc60e.tar.gz

###### Dependencies
- protobuf-compiler
- libgoogle-glog-dev
- libgflags-dev
- libprotobuf-dev
- libgtest-dev

###### Patch
```shell
git apply puffin.patch
```

###### Build
```shell
protoc -Isrc --cpp_out=src src/puffin.proto
make
sudo cp puffin_binary /usr/local/bin/puffin
```
