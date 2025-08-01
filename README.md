# pico-sdk partial tree

https://github.com/raspberrypi/pico-sdk

This is just a partial copy of the pico-sdk repository to reduce repository size.
The following paths are extracted:

- `LICENSE.TXT`
- `src/rp2040/hardware_regs/include`
- `src/rp2040/hardware_structs/include`
- `src/rp2_common/cmsis/stub/CMSIS/Device/RP2040/Include`
- `src/rp2350/hardware_regs/include`
- `src/rp2350/hardware_structs/include`
- `src/rp2_common/cmsis/stub/CMSIS/Device/RP2350/Include`
- `tools/pioasm/`

Boot2 variants are built from `src/rp2040/boot_stage2` and `src/rp2350/boot_stage2`.
The stand-alone `pioasm` can be compiled as such:

```sh
mkdir -p pioasm/build && cd pioasm/build
cmake .. && make
```

This repository is updated periodically by Github Actions.
