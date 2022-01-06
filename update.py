#!/usr/bin/env python3

import os
import sys
import json
import shutil
import fnmatch
import subprocess
import binascii
import struct
from pathlib import Path
import urllib.request

source_paths = [
    ["","LICENSE.TXT"],
    ["src/rp2040/hardware_regs","include/*/*/*h"],
    ["src/rp2040/hardware_structs","include/*/*/*.h"],
    ["src/rp2_common/cmsis/stub/CMSIS/Device/RaspberryPi/RP2040/Include","*.h","include"],
]

boot2_variants = [
	"generic_03h",
	"at25sf128a",
	"is25lp080",
	"w25q080",
	"w25x10cl"
]

def run(where, command, stdin=None):
	print(command)
	result = subprocess.run(command, shell=True, cwd=where, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if result.returncode != 0:
		print('failed exec command ' + command)
		print(result.stderr.decode("utf-8").strip(" \n"))
		exit(1)
	return (result.returncode,
	        result.stdout.decode("utf-8").strip(" \n"),
	        result.stderr.decode("utf-8").strip(" \n"))

def bitrev(x, width):
    return int("{:0{w}b}".format(x, w=width)[::-1], 2)


with urllib.request.urlopen("https://api.github.com/repos/raspberrypi/pico-sdk/releases/latest") as response:
   tag = json.loads(response.read())["tag_name"]

# clone the repository
if "--fast" not in sys.argv:
    print("Cloning pico-sdk repository at tag v{}...".format(tag))
    shutil.rmtree("pico_sdk_src", ignore_errors=True)
    subprocess.run("git clone --depth=1 --branch {} ".format(tag) +
                   "https://github.com/raspberrypi/pico-sdk.git pico_sdk_src", shell=True)

# remove the sources in this repo
shutil.rmtree("include", ignore_errors=True)


print("Copying pico-sdk headers...")
for pattern_conf in source_paths:
    src_path = os.path.join("pico_sdk_src",pattern_conf[0])
    pattern = pattern_conf[1]
    for path in Path(src_path).glob(pattern):
        if not path.is_file(): continue
        dest = path.relative_to(src_path)
        if len(pattern_conf) > 2:
        	dest = Path(pattern_conf[2]) / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(dest)
        # Copy, normalize newline and remove trailing whitespace
        with path.open("r", newline=None, encoding="utf-8", errors="replace") as rfile, \
                           dest.open("w", encoding="utf-8") as wfile:
            wfile.writelines(l.rstrip()+"\n" for l in rfile.readlines())

print("Building boot2 varints...")

for variant in boot2_variants:
	
	builddir = Path('build/boot2_' + variant)
	if not builddir.exists():
		builddir.mkdir(parents=True, exist_ok=True)
	run(builddir,"cmake ../../pico_sdk_src -G \"Unix Makefiles\" -DPICO_DEFAULT_BOOT_STAGE2=boot2_" + variant)
	run(builddir,'make bs2_default_padded_checksummed_asm') # for validate
	#run(builddir,'make bs2_default_bin')
	ifile = os.path.join(builddir,'src/rp2_common/boot_stage2/bs2_default.bin')
	try:
	    idata = open(ifile, "rb").read()
	except:
		sys.exit("Could not open input file '{}'".format(ifile))
	pad = 256
	if len(idata) >= pad - 4:
		sys.exit("Input file size ({} bytes) too large for final size ({} bytes)".format(len(idata), pad))
	idata_padded = idata + bytes(pad - 4 - len(idata))
	seed = 0xffffffff
	# Our bootrom CRC32 is slightly bass-ackward but it's best to work around for now (FIXME)
	# 100% worth it to save two Thumb instructions
	checksum = bitrev(
	    (binascii.crc32(bytes(bitrev(b, 8) for b in idata_padded), seed ^ 0xffffffff) ^ 0xffffffff) & 0xffffffff, 32)
	odata = idata_padded + struct.pack("<L", checksum)

	ofilename = 'src/boot2_' + variant + '.cpp'
	try:
		Path(ofilename).parent.mkdir(parents=True, exist_ok=True)
		with open(ofilename, "w") as ofile:
			ofile.write("// Stage2 bootloader\n\n")
			ofile.write("#include <cstdint>\n")
			ofile.write("extern \"C\" __attribute__((section(\".boot2\"))) const uint8_t boot2[256] = {\n")
			for offs in range(0, len(odata), 16):
				chunk = odata[offs:min(offs + 16, len(odata))]
				ofile.write("\t {},\n".format(", ".join("0x{:02x}".format(b) for b in chunk)))
			ofile.write("};\n")
	except:
		sys.exit("Could not open output file '{}'".format(ofilename))

subprocess.run("git add src include LICENSE.TXT", shell=True)
if subprocess.call("git diff-index --quiet HEAD --", shell=True):
    subprocess.run('git commit -m "Update pico-sdk to v{}"'.format(tag), shell=True)
