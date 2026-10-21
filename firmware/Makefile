all : build

TARGET:=pdcard
TARGET_MCU:=CH32X035
TARGET_MCU_PACKAGE:=CH32X035G8U6

# make LOG=1: print the charger's capabilities over the debug link (make log)
ifeq ($(LOG),1)
	EXTRA_CFLAGS+=-DPDCARD_LOG=1
endif

# make CCDIAG=1: LEDs show what the CC comparators see, no PD (README)
ifeq ($(CCDIAG),1)
	EXTRA_CFLAGS+=-DPDCARD_CCDIAG=1
endif

# Programmer: YD-RP2040 running the mtabini/ch32fun Pico programmer (Ardulink)
PORT?=/dev/ttyACM0
MINICHLINK_ARGS=-C ardulink -c $(PORT)
FLASH_COMMAND=$(MINICHLINK)/minichlink $(MINICHLINK_ARGS) -w $< $(WRITE_SECTION) -b

include ch32fun/ch32fun/ch32fun.mk

flash : cv_flash
clean : cv_clean

# Check the programmer sees the chip before writing anything
detect : $(MINICHLINK)/minichlink
	$(MINICHLINK)/minichlink $(MINICHLINK_ARGS) -i

# Debug printf terminal (needs a LOG=1 build). Connecting reboots the chip, so start this
# before plugging in a charger, or the charger keeps its old contract and never resends caps.
log : $(MINICHLINK)/minichlink
	$(MINICHLINK)/minichlink $(MINICHLINK_ARGS) -T

# Attach without rebooting (-kT; -k only works combined), to read a PD trace already in RAM
logkeep : $(MINICHLINK)/minichlink
	$(MINICHLINK)/minichlink $(MINICHLINK_ARGS) -kT

.PHONY : all flash clean detect log logkeep
