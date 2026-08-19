#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <ctime>
#include <limits>

typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef int8_t int8;
typedef int16_t int16;
typedef int32_t int32;

static time_t scripted_time = 0;
#define time(ignored_argument) (scripted_time)

static uint8 cartridge_clock_bytes[20];
static uint8 open_bus = 0x00;
static uint8 cartridge_rom[1] = { 0 };
static bool cartridge_has_clock = true;

#define memory_cartrtc_read(a)          cartridge_clock_bytes[(a)]
#define memory_cartrtc_write(a, b)      { cartridge_clock_bytes[(a)] = (b); }
#define memory_cartrom_size()           1
#define memory_cartrom_read(a)          cartridge_rom[0]
#define cartridge_info_spc7110rtc       cartridge_has_clock
#define cpu_regs_mdr                    open_bus

static inline unsigned max(unsigned a, unsigned b) { return a > b ? a : b; }
static inline unsigned min(unsigned a, unsigned b) { return a < b ? a : b; }

#include "srtcemu.h"
#include "srtcemu.cpp"

#define SPC7110_DECOMP_BUFFER_SIZE 64
#include "spc7110dec.h"
#include "spc7110dec.cpp"
#include "spc7110emu.h"
#include "spc7110emu.cpp"

static SRTC sharp_clock;
static SPC7110 epson_host;

static bool addressed_to_epson(unsigned address) {
  return address >= 0x4840 && address <= 0x4842;
}

static void power_everything(void) {
  memset(cartridge_clock_bytes, 0, sizeof(cartridge_clock_bytes));
  sharp_clock.power();
  epson_host.power();
  open_bus = 0x00;
}

static uint8 read_from(unsigned address) {
  if (addressed_to_epson(address)) return epson_host.mmio_read(address);
  return sharp_clock.mmio_read(address);
}

static void write_to(unsigned address, uint8 value) {
  if (addressed_to_epson(address)) {
    epson_host.mmio_write(address, value);
    return;
  }
  sharp_clock.mmio_write(address, value);
}

int main(void) {
  char line[256];
  power_everything();

  while (fgets(line, sizeof(line), stdin)) {
    char verb[32];
    long first = 0, second = 0;
    if (sscanf(line, "%31s %li %li", verb, &first, &second) < 1) continue;

    if (!strcmp(verb, "time")) {
      scripted_time = (time_t)first;
    } else if (!strcmp(verb, "store")) {
      cartridge_clock_bytes[first % 20] = (uint8)second;
    } else if (!strcmp(verb, "power")) {
      power_everything();
    } else if (!strcmp(verb, "r")) {
      printf("%02X\n", read_from((unsigned)first));
    } else if (!strcmp(verb, "w")) {
      write_to((unsigned)first, (uint8)second);
    } else if (!strcmp(verb, "dump")) {
      for (int at = 0; at < 20; at++) printf("%02X", cartridge_clock_bytes[at]);
      printf("\n");
    }
  }
  return 0;
}
