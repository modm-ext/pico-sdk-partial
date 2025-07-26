#!/usr/bin/env python3

import sys
import shutil
import subprocess
import binascii
import struct
from pathlib import Path

# wget -qL https://raw.githubusercontent.com/modm-ext/partial/main/partial.py
import partial
partial.keepalive()

repo = "raspberrypi/pico-sdk"
src = Path("pico_sdk_src")
platforms = {
    "rp2040": "rp2040",
    "rp2350": "rp2350-arm-s"
}

tag = partial.latest_release_tag(repo)
partial.clone_repo(repo, src, branch=tag, overwrite="--fast" not in sys.argv)
shutil.rmtree("src", ignore_errors=True)
files = [Path("src")]
files += partial.copy_files(src, ["LICENSE.TXT"])
files += partial.copy_files(Path("pico_sdk_src/tools"), ["pioasm/**/*.[hct]*"])
for target in platforms:
    files += partial.copy_files(Path(f"pico_sdk_src/src/{target}/hardware_regs/include/"), ["**/*.h"], dest=target)
    files += partial.copy_files(Path(f"pico_sdk_src/src/{target}/hardware_structs/include/"), ["**/*.h"], dest=target, delete=False)
    files += partial.copy_files(Path(f"pico_sdk_src/src/rp2_common/cmsis/stub/CMSIS/Device/{target.upper()}/Include/"), ["*.h"], dest=target, delete=False)


print("Building boot2 variants...")
# See https://github.com/raspberrypi/pico-sdk/issues/2126
boot2_variants = {
    "generic_03h": ["rp2040", "rp2350"],
    "at25sf128a": ["rp2040"],
    "is25lp080": ["rp2040"],
    "w25q080": ["rp2040", "rp2350"],
    "w25x10cl": ["rp2040"],
}
def run(where, command, stdin=None):
    print(command)
    result = subprocess.run(command, shell=True, cwd=where, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"Failed exec command: '{command}'")
        print(result.stderr.decode("utf-8").strip(" \n"))
        exit(1)
    return (result.returncode,
            result.stdout.decode("utf-8").strip(" \n"),
            result.stderr.decode("utf-8").strip(" \n"))

def bitrev(x, width):
    return int("{:0{w}b}".format(x, w=width)[::-1], 2)

for variant, targets in boot2_variants.items():
    for target in targets:
        builddir = Path(f"build/boot2_{variant}_{target}")
        builddir.mkdir(parents=True, exist_ok=True)

        run(builddir, f'cmake ../../pico_sdk_src -G "Unix Makefiles" -DPICO_DEFAULT_BOOT_STAGE2=boot2_{variant} -DPICO_PLATFORM={platforms[target]}')
        run(builddir, "make bs2_default_bin") # for validate
        #run(builddir,'make bs2_default_bin')
        ifile = builddir / f"src/{target}/boot_stage2/bs2_default.bin"
        try:
            idata = open(ifile, "rb").read()
        except:
            sys.exit(f"Could not open input file '{ifile}'")
        pad = 256
        if len(idata) >= pad - 4:
            sys.exit(f"Input file size ({len(idata)} bytes) too large for final size ({pad} bytes)")
        idata_padded = idata + bytes(pad - 4 - len(idata))
        seed = 0xffffffff
        # Our bootrom CRC32 is slightly bass-ackward but it's best to work around for now (FIXME)
        # 100% worth it to save two Thumb instructions
        checksum = bitrev(
            (binascii.crc32(bytes(bitrev(b, 8) for b in idata_padded), seed ^ 0xffffffff) ^ 0xffffffff) & 0xffffffff, 32)
        odata = idata_padded + struct.pack("<L", checksum)

        ofilename = Path(f"src/boot2_{target}_{variant}.cpp")
        try:
            ofilename.parent.mkdir(parents=True, exist_ok=True)
            with ofilename.open("w") as ofile:
                ofile.write("// Stage2 bootloader\n\n")
                ofile.write("#include <cstdint>\n")
                ofile.write('extern "C" __attribute__((section(".boot2"))) const uint8_t boot2[256] = {\n')
                for offs in range(0, len(odata), 16):
                    chunk = odata[offs:min(offs + 16, len(odata))]
                    ofile.write("\t {},\n".format(", ".join(f"0x{b:02x}" for b in chunk)))
                ofile.write("};\n")
        except:
            sys.exit("Could not open output file '{}'".format(ofilename))

partial.commit(files, tag)
