# Firmware toolchain for the CH32X035 (RISC-V rv32imac, no FPU).
#
#   nix-shell            # from firmware/
#   make                 # build pdcard.bin
#   make flash PORT=/dev/ttyACM0
#
# Prebuilt nixpkgs cross GCC. Its libgcc is hard-float (rv32gc / ilp32d), so if
# the code ever needs a libgcc helper (64-bit division, float) the link fails
# with a float-ABI error. Today nothing pulls from libgcc.
{ pkgs ? import <nixpkgs> { } }:

pkgs.mkShell {
  packages = [
    pkgs.pkgsCross.riscv32-embedded.buildPackages.gcc # riscv32-none-elf-gcc, binutils
    pkgs.gnumake
    # minichlink (built from the ch32fun submodule on first `make flash`)
    pkgs.pkg-config
    pkgs.libusb1
    pkgs.systemd # libudev
  ];

  # ch32fun.mk only auto-detects riscv64-* / riscv-none-elf prefixes.
  PREFIX = "riscv32-none-elf";

  # Nix hardening flags (-z relro, -z now) mean nothing for bare-metal firmware
  hardeningDisable = [ "all" ];
}
