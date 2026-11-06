/*
 * extcsd_read.c — 只读读取 eMMC 的 EXT_CSD（CMD8 SEND_EXT_CSD）
 *
 * 安全性: 只发一条只读命令，不写任何寄存器、不改卡片状态。
 *         与 mmc-utils 的 `mmc extcsd read` 等价。
 *
 * 编译: gcc -O2 -o extcsd_read extcsd_read.c
 * 用法: ./extcsd_read [/dev/mmcblk1]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <errno.h>
#include <linux/mmc/ioctl.h>

/*
 * 内核 UAPI 的 <linux/mmc/ioctl.h> 只导出 struct mmc_ioc_cmd 和 MMC_IOC_CMD，
 * 不导出命令/响应标志宏（那些在 mmc-utils 自己的头里）。
 * 这里按内核 include/linux/mmc/mmc.h 的位定义补齐，数值与 mmc-utils 完全一致。
 */
#ifndef MMC_RSP_PRESENT
#define MMC_RSP_PRESENT   (1 << 0)
#define MMC_RSP_CRC       (1 << 1)
#define MMC_RSP_OPCODE    (1 << 2)
#define MMC_RSP_SPI_S1    (1 << 7)

#define MMC_RSP_R1        (MMC_RSP_PRESENT | MMC_RSP_CRC | MMC_RSP_OPCODE)  /* 0x07 */
#define MMC_RSP_SPI_R1    (MMC_RSP_SPI_S1)                                  /* 0x80 */

#define MMC_CMD_MASK      (3 << 5)
#define MMC_CMD_ADTC      (1 << 5)                                          /* 0x20 */
#endif

static const char *devtype_bits[] = {
    "High Speed (26/52 MHz)",
    "HS200 (200 MHz SDR, 1.8V)",
    "HS400 (200 MHz DDR)",
    "HS400 Enhanced Strobe",
};

static void dump(const char *label, const unsigned char *b, int off, int len)
{
    printf("  %-28s [%3d..%3d] ", label, off, off + len - 1);
    for (int i = 0; i < len; i++) printf("%02x ", b[off + i]);
    printf("\n");
}

int main(int argc, char **argv)
{
    const char *dev = argc > 1 ? argv[1] : "/dev/mmcblk1";
    unsigned char csd[512];
    struct mmc_ioc_cmd cmd;
    int fd;

    fd = open(dev, O_RDONLY | O_NONBLOCK);
    if (fd < 0) { perror("open"); return 1; }

    memset(csd, 0, sizeof(csd));
    memset(&cmd, 0, sizeof(cmd));
    cmd.write_flag = 0;
    cmd.opcode     = 8;                 /* SEND_EXT_CSD */
    cmd.arg        = 0;
    cmd.flags      = MMC_RSP_SPI_R1 | MMC_RSP_R1 | MMC_CMD_ADTC;
    cmd.blksz      = 512;
    cmd.blocks     = 1;
    mmc_ioc_cmd_set_data(cmd, csd);

    if (ioctl(fd, MMC_IOC_CMD, &cmd) < 0) {
        perror("ioctl MMC_IOC_CMD");
        close(fd);
        return 1;
    }
    close(fd);

    unsigned int sec_count = csd[212] | (csd[213] << 8) | (csd[214] << 16) | ((unsigned)csd[215] << 24);

    printf("=== EXT_CSD @ %s ===\n", dev);
    printf("  EXT_CSD_REV                  [192] = %u\n", csd[192]);
    printf("  CSD_STRUCTURE                [194] = %u\n", csd[194]);

    printf("\n--- 能力 (决定能不能提速) ---\n");
    printf("  DEVICE_TYPE                  [196] = 0x%02x\n", csd[196]);
    for (int i = 0; i < 4; i++)
        printf("      bit%d %-26s : %s\n", i, devtype_bits[i],
               (csd[196] & (1 << i)) ? "支持" : "不支持");
    printf("  SEC_FEATURE_SUPPORT          [231] = 0x%02x\n", csd[231]);
    printf("  POWER_CLASS                  [187] = 0x%02x\n", csd[187]);

    printf("\n--- 当前配置 ---\n");
    printf("  BUS_WIDTH                    [183] = %u  (%s)\n", csd[183],
           csd[183] == 0 ? "1-bit" : csd[183] == 1 ? "4-bit" : csd[183] == 2 ? "8-bit" : "?");
    printf("  HS_TIMING                    [185] = %u  (%s)\n", csd[185],
           csd[185] == 0 ? "backward compatible" :
           csd[185] == 1 ? "high speed" :
           csd[185] == 2 ? "HS200" : csd[185] == 3 ? "HS400" : "?");
    printf("  PARTITION_CONFIG             [179] = 0x%02x\n", csd[179]);
    printf("  BOOT_BUS_WIDTH               [177] = 0x%02x\n", csd[177]);

    printf("\n--- 容量 ---\n");
    printf("  SEC_COUNT                    [212..215] = %u sectors = %.1f GiB\n",
           sec_count, sec_count * 512.0 / (1024.0 * 1024.0 * 1024.0));
    printf("  RPMB_SIZE_MULT               [168] = %u  (x128KB = %u KB)\n",
           csd[168], csd[168] * 128);

    printf("\n--- 健康度 ---\n");
    printf("  PRE_EOL_INFO                 [267] = 0x%02x  (%s)\n", csd[267],
           csd[267] == 1 ? "正常" : csd[267] == 2 ? "警告: 80% 寿命" :
           csd[267] == 3 ? "紧急: 90% 寿命" : "?");
    printf("  DEVICE_LIFE_TIME_EST_TYP_A   [268] = 0x%02x  (SLC: %s)\n", csd[268],
           csd[268] == 0 ? "未定义" : "已用 10% x 值");
    printf("  DEVICE_LIFE_TIME_EST_TYP_B   [269] = 0x%02x  (MLC: %s)\n", csd[269],
           csd[269] == 0 ? "未定义" : "已用 10% x 值");
    printf("  CACHE_SIZE                   [249..252] = %u KB\n",
           (unsigned)(csd[249] | (csd[250] << 8) | (csd[251] << 16) | ((unsigned)csd[252] << 24)));

    printf("\n--- 关键字段十六进制 ---\n");
    dump("DEVICE_TYPE", csd, 196, 1);
    dump("BUS_WIDTH/HS_TIMING", csd, 183, 4);
    dump("SEC_COUNT", csd, 212, 4);
    dump("PARTITION_CONFIG", csd, 179, 1);
    dump("PRE_EOL / LIFE_TIME", csd, 267, 3);

    printf("\n--- 完整 512 字节 ---\n");
    for (int i = 0; i < 512; i += 16) {
        printf("  %3d: ", i);
        for (int j = 0; j < 16; j++) printf("%02x ", csd[i + j]);
        printf("\n");
    }
    return 0;
}
