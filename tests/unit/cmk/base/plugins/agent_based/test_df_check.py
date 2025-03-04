#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GMiBH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Iterable

import pytest

from cmk.base.plugins.agent_based import df
from cmk.base.plugins.agent_based.agent_based_api.v1 import Metric, Result, Service, State
from cmk.base.plugins.agent_based.df_section import parse_df

#   .--Test info sections--------------------------------------------------.
#   |                _____         _     _        __                       |
#   |               |_   _|__  ___| |_  (_)_ __  / _| ___                  |
#   |                 | |/ _ \/ __| __| | | '_ \| |_ / _ \                 |
#   |                 | |  __/\__ \ |_  | | | | |  _| (_) |                |
#   |                 |_|\___||___/\__| |_|_| |_|_|  \___/                 |
#   |                                                                      |
#   |                               _   _                                  |
#   |                 ___  ___  ___| |_(_) ___  _ __  ___                  |
#   |                / __|/ _ \/ __| __| |/ _ \| '_ \/ __|                 |
#   |                \__ \  __/ (__| |_| | (_) | | | \__ \                 |
#   |                |___/\___|\___|\__|_|\___/|_| |_|___/                 |
#   |                                                                      |
#   '----------------------------------------------------------------------'

info_df_lnx = [
    ["/dev/sda4", "ext4", "143786696", "101645524", "34814148", "75%", "/"],
    ["[df_inodes_start]"],
    ["/dev/sda4", "ext4", "9142272", "1654272", "7488000", "19%", "/"],
    ["[df_inodes_end]"],
]

info_df_win = [
    ["C:\\", "NTFS", "8192620", "7724268", "468352", "95%", "C:\\"],
    ["New_Volume", "NTFS", "10240796", "186256", "10054540", "2%", "E:\\"],
    ["New_Volume", "NTFS", "124929596", "50840432", "74089164", "41%", "F:\\"],
]

# fmt: off
info_df_lnx_docker = [
    ['/dev/sda2', 'ext4', '143786696', '101645524', '34814148', '75%', '/var/lib/docker'],
    ['/dev/sda3', 'ext4', '143786696', '101645524', '34814148', '75%', '/var/lib/docker-latest'],
    ['/dev/sda4', 'ext4', '143786696', '101645524', '34814148', '75%', '/var/lib/docker/some-fs/mnt/grtzlhash'],
    ['/dev/sdb1', 'ext4', '131586052', '75701024', '49157812', '61%', '/var/lib/docker/volumes'],
    ['[df_inodes_start]'],
    ['/dev/sda2', 'ext4', '9142272', '1654272', '7488000', '19%', '/var/lib/docker'],
    ['/dev/sda3', 'ext4', '9142272', '1654272', '7488000', '19%', '/var/lib/docker-latest'],
    ['/dev/sda4', 'ext4', '9142272', '1654272', '7488000', '19%', '/var/lib/docker/some-fs/mnt/grtzlhash'],
    ['/dev/sdb1', 'ext4', '8388608', '586810', '7801798', '7%', '/var/lib/docker/volumes'],
    ['[df_inodes_end]'],
]
# fmt: on

info_df_lnx_tmpfs = [
    ["tmpfs", "tmpfs", "8152820", "76", "8152744", "1%", "/opt/omd/sites/heute/tmp"],
    ["tmpfs", "tmpfs", "8152840", "118732", "8034108", "2%", "/dev/shm"],
    ["[df_inodes_start]"],
    ["tmpfs", "tmpfs", "2038205", "48", "2038157", "1%", "/opt/omd/sites/heute/tmp"],
    ["tmpfs", "tmpfs", "2038210", "57", "2038153", "1%", "/dev/shm"],
    ["[df_inodes_end]"],
]

# NOTE: This gargantuan test info section is uncritically used data from an archived agent output.
#       I suspect that our handling of btrfs is not really adequate, test cases using this data
#       serve the sole purpose of not inadvertenty breaking the status quo. Thus:
# TODO: Replace this monstrosity with something more concise.
# fmt: off
info_df_btrfs = [
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/'],
    ['devtmpfs', 'devtmpfs', '497396', '0', '497396', '0%', '/dev'],
    ['tmpfs', 'tmpfs', '506312', '0', '506312', '0%', '/dev/shm'],
    ['tmpfs', 'tmpfs', '506312', '6980', '499332', '2%', '/run'],
    ['tmpfs', 'tmpfs', '506312', '0', '506312', '0%', '/sys/fs/cgroup'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/.snapshots'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/tmp'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/spool'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/opt'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/log'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/lib/pgsql'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/lib/named'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/lib/mailman'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/var/crash'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/usr/local'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/tmp'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/srv'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/opt'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/home'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/boot/grub2/x86_64-efi'],
    ['/dev/sda1', 'btrfs', '20970496', '4169036', '16539348', '21%', '/boot/grub2/i386-pc'],
    ['[df_inodes_start]'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/'],
    ['devtmpfs', 'devtmpfs', '124349', '371', '123978', '1%', '/dev'],
    ['tmpfs', 'tmpfs', '126578', '1', '126577', '1%', '/dev/shm'],
    ['tmpfs', 'tmpfs', '126578', '481', '126097', '1%', '/run'],
    ['tmpfs', 'tmpfs', '126578', '12', '126566', '1%', '/sys/fs/cgroup'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/.snapshots'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/tmp'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/spool'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/opt'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/log'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/lib/pgsql'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/lib/named'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/lib/mailman'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/var/crash'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/usr/local'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/tmp'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/srv'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/opt'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/home'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/boot/grub2/x86_64-efi'],
    ['/dev/sda1', 'btrfs', '0', '0', '0', '-', '/boot/grub2/i386-pc'],
    ['[df_inodes_end]'],
    ['[df_lsblk_start]'],
    ['{'],
    ['"blockdevices":', '['],
    ['{"name":"/dev/sda1",', '"uuid":"12345678-9012-3456-7890-123456789012"}'],
    [']'],
    ['}'],
    ['[df_lsblk_end]']
]
# fmt: on

info_empty_inodes = [
    ["[df_inodes_start]"],
    ["/dev/mapper/vgdns-lvbindauthlog", "-", "-", "-", "-", "-", "/dns/bindauth/log"],
    ["[df_inodes_end]"],
]

# .
#   .--Test functions------------------------------------------------------.
#   |   _____         _      __                  _   _                     |
#   |  |_   _|__  ___| |_   / _|_   _ _ __   ___| |_(_) ___  _ __  ___     |
#   |    | |/ _ \/ __| __| | |_| | | | '_ \ / __| __| |/ _ \| '_ \/ __|    |
#   |    | |  __/\__ \ |_  |  _| |_| | | | | (__| |_| | (_) | | | \__ \    |
#   |    |_|\___||___/\__| |_|  \__,_|_| |_|\___|\__|_|\___/|_| |_|___/    |
#   |                                                                      |
#   '----------------------------------------------------------------------'


@pytest.mark.parametrize(
    "info,expected_result,inventory_df_rules",
    [
        (
            [],
            [],
            {},
        ),
        # Linux:
        (
            info_df_lnx,
            [
                (
                    "/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {},
        ),
        # Linux w/ volume name unset:
        (
            info_df_lnx,
            [
                (
                    "/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "item_appearance": "mountpoint",
            },
        ),
        # Linux w/ volume name option:
        (
            info_df_lnx,
            [
                (
                    "/dev/sda4 /",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "item_appearance": "volume_name_and_mountpoint",
            },
        ),
        # Windows:
        (
            info_df_win,
            [
                (
                    "E:/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "F:/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "C:/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {},
        ),
        # Windows w/ volume name option:
        (
            info_df_win,
            [
                (
                    "New_Volume E:/",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "New_Volume F:/",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "C:\\ C:/",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "item_appearance": "volume_name_and_mountpoint",
            },
        ),
        # Ignoring tmpfs:
        (
            info_df_lnx_tmpfs,
            [],
            {},
        ),
        # Ignoring tmpfs explicitly:
        (
            info_df_lnx_tmpfs,
            [],
            {"ignore_fs_types": ["tmpfs", "nfs", "sMiBfs", "cifs", "iso9660"]},
        ),
        # Ignoring tmpfs explicitly, but including one mountpoint explicitly:
        (
            info_df_lnx_tmpfs,
            [
                (
                    "/opt/omd/sites/heute/tmp",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "ignore_fs_types": ["tmpfs", "nfs", "sMiBfs", "cifs", "iso9660"],
                "never_ignore_mountpoints": ["/opt/omd/sites/heute/tmp"],
            },
        ),
        # Including tmpfs:
        (
            info_df_lnx_tmpfs,
            [
                (
                    "/opt/omd/sites/heute/tmp",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/shm",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {"ignore_fs_types": ["nfs", "sMiBfs", "cifs", "iso9660"]},
        ),
        # Including tmpfs and volume name:
        (
            info_df_lnx_tmpfs,
            [
                (
                    "tmpfs /opt/omd/sites/heute/tmp",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "tmpfs /dev/shm",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "ignore_fs_types": ["nfs", "sMiBfs", "cifs", "iso9660"],
                "item_appearance": "volume_name_and_mountpoint",
            },
        ),
        # Including only check mk tmpfs via regex
        (
            info_df_lnx_tmpfs,
            [
                (
                    "tmpfs /opt/omd/sites/heute/tmp",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "ignore_fs_types": ["tmpfs", "nfs", "sMiBfs", "cifs", "iso9660"],
                "item_appearance": "volume_name_and_mountpoint",
                "never_ignore_mountpoints": ["~.*/omd/sites/[^/]+/tmp$"],
            },
        ),
        # btrfs:
        (
            info_df_btrfs,
            [
                (
                    "btrfs /dev/sda1",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {},
        ),
        # btrfs w/ volume name option:
        (
            info_df_btrfs,
            [
                (
                    "/dev/sda1 btrfs /dev/sda1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {
                "item_appearance": "volume_name_and_mountpoint",
            },
        ),
        # empty inodes:
        (info_empty_inodes, [], {}),
        # Omit docker container filesystems, but not /var/lib/docker{,-latest}:
        (
            info_df_lnx_docker,
            [
                (
                    "/var/lib/docker",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/var/lib/docker-latest",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
            {},
        ),
        # btrfs with uuid as mountpoint
        (
            info_df_btrfs,
            [
                (
                    "btrfs 12345678-9012-3456-7890-123456789012",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "uuid",
                    },
                ),
            ],
            {
                "mountpoint_for_block_devices": "uuid_as_mountpoint",
            },
        ),
    ],
)
def test_df_discovery_with_parse(  # type:ignore[no-untyped-def]
    info, expected_result, inventory_df_rules
) -> None:
    assert sorted(df.discover_df(inventory_df_rules, parse_df(info))) == sorted(
        Service(item=i, parameters=p) for i, p in expected_result
    )


def make_test_df_params():
    return {
        "trend_range": 24,
        "show_levels": "onmagic",
        "inodes_levels": (10.0, 5.0),
        "magic_normsize": 20,
        "show_inodes": "onlow",
        "levels": (80.0, 90.0),
        "show_reserved": False,
        "levels_low": (50.0, 60.0),
        "trend_perfdata": True,
    }


def _extract_value_to_mock_for_zero_growth(results: Iterable[Result | Metric]) -> float:
    for r in results:
        if isinstance(r, Metric) and r.name == "fs_used":
            return r.value
    return 0.0


@pytest.mark.parametrize(
    "item, counter, params ,info, expected_result",
    [
        (
            "/",
            "/",
            make_test_df_params(),
            info_df_lnx,
            [
                Metric(
                    "fs_used",
                    106418.50390625,
                    levels=(112333.35624980927, 126375.0257806778),
                    boundaries=(0.0, 140416.6953125),
                ),
                Metric("fs_free", 33998.19140625, boundaries=(0, None)),
                Metric(
                    "fs_used_percent",
                    75.78764310712029,
                    levels=(79.99999999986416, 89.99999999959249),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 75.79% - 104 GiB of 137 GiB"),
                Metric("fs_size", 140416.6953125, boundaries=(0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 5850.695638020833)),
                Metric(
                    "inodes_used",
                    1654272.0,
                    levels=(8228044.8, 8685158.4),
                    boundaries=(0.0, 9142272.0),
                ),
                Result(
                    state=State.OK,
                    notice="Inodes used: 18.09%, Inodes available: 7,488,000 (81.91%)",
                ),
            ],
        ),
        (
            "/dev/sda4 /",
            "/",
            make_test_df_params(),
            info_df_lnx,
            [
                Metric(
                    "fs_used",
                    106418.50390625,
                    levels=(112333.35624980927, 126375.0257806778),
                    boundaries=(0.0, 140416.6953125),
                ),
                Metric("fs_free", 33998.19140625, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    75.78764310712029,
                    levels=(79.99999999986416, 89.99999999959249),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 75.79% - 104 GiB of 137 GiB"),
                Metric("fs_size", 140416.6953125, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 5850.695638020833)),
                Metric(
                    "inodes_used",
                    1654272.0,
                    levels=(8228044.8, 8685158.4),
                    boundaries=(0.0, 9142272.0),
                ),
                Result(
                    state=State.OK,
                    notice="Inodes used: 18.09%, Inodes available: 7,488,000 (81.91%)",
                ),
            ],
        ),
        (
            "E:/",
            "E:/",
            make_test_df_params(),
            info_df_win,
            [
                Metric(
                    "fs_used",
                    181.890625,
                    levels=(8000.621874809265, 9000.699608802795),
                    boundaries=(0.0, 10000.77734375),
                ),
                Metric("fs_free", 9818.88671875, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    1.8187648694496013,
                    levels=(79.9999999980928, 89.9999999942784),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 1.82% - 182 MiB of 9.77 GiB"),
                Metric("fs_size", 10000.77734375, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 416.6990559895833)),
            ],
        ),
        (
            "New_Volume E:/",
            "E:/",
            make_test_df_params(),
            info_df_win,
            [
                Metric(
                    "fs_used",
                    181.890625,
                    levels=(8000.621874809265, 9000.699608802795),
                    boundaries=(0.0, 10000.77734375),
                ),
                Metric("fs_free", 9818.88671875, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    1.8187648694496013,
                    levels=(79.9999999980928, 89.9999999942784),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 1.82% - 182 MiB of 9.77 GiB"),
                Metric("fs_size", 10000.77734375, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 416.6990559895833)),
            ],
        ),
        (
            "btrfs /dev/sda1",
            "btrfs /dev/sda1",
            make_test_df_params(),
            info_df_btrfs,
            [
                Metric(
                    "fs_used",
                    4327.29296875,
                    levels=(16383.199999809265, 18431.099999427795),
                    boundaries=(0.0, 20479.0),
                ),
                Metric("fs_free", 16151.70703125, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    21.130391956394355,
                    levels=(79.99999999906863, 89.99999999720589),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 21.13% - 4.23 GiB of 20.0 GiB"),
                Metric("fs_size", 20479.0, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 853.2916666666666)),
            ],
        ),
        (
            "/home",
            "/home",
            make_test_df_params(),
            info_df_lnx,
            [],
        ),
        (
            "btrfs /dev/sda1",
            "btrfs /dev/sda1",
            {**make_test_df_params(), "show_volume_name": True},
            info_df_btrfs,
            [
                Result(state=State.OK, summary="[/dev/sda1]"),
                Metric(
                    "fs_used",
                    4327.29296875,
                    levels=(16383.199999809265, 18431.099999427795),
                    boundaries=(0.0, 20479.0),
                ),
                Metric("fs_free", 16151.70703125, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    21.130391956394355,
                    levels=(79.99999999906863, 89.99999999720589),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 21.13% - 4.23 GiB of 20.0 GiB"),
                Metric("fs_size", 20479.0, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 853.2916666666666)),
            ],
        ),
        (
            "btrfs /dev/sda1",
            "btrfs /dev/sda1",
            make_test_df_params(),
            info_df_btrfs,
            [
                Metric(
                    "fs_used",
                    4327.29296875,
                    levels=(16383.199999809265, 18431.099999427795),
                    boundaries=(0.0, 20479.0),
                ),
                Metric("fs_free", 16151.70703125, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    21.130391956394355,
                    levels=(79.99999999906863, 89.99999999720589),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 21.13% - 4.23 GiB of 20.0 GiB"),
                Metric("fs_size", 20479.0, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 853.2916666666666)),
            ],
        ),
        # btrfs with uuid as mountpoint
        (
            "btrfs 12345678-9012-3456-7890-123456789012",
            "btrfs 12345678-9012-3456-7890-123456789012",
            {
                **make_test_df_params(),
                "mountpoint_for_block_devices": "uuid",
            },
            info_df_btrfs,
            [
                Metric(
                    "fs_used",
                    4327.29296875,
                    levels=(16383.199999809265, 18431.099999427795),
                    boundaries=(0.0, 20479.0),
                ),
                Metric("fs_free", 16151.70703125, boundaries=(0.0, None)),
                Metric(
                    "fs_used_percent",
                    21.130391956394355,
                    levels=(79.99999999906863, 89.99999999720589),
                    boundaries=(0.0, 100.0),
                ),
                Result(state=State.OK, summary="Used: 21.13% - 4.23 GiB of 20.0 GiB"),
                Metric("fs_size", 20479.0, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 853.2916666666666)),
            ],
        ),
    ],
)
def test_df_check_with_parse(  # type:ignore[no-untyped-def]
    item, counter: str, params, info, expected_result, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        df,
        "get_value_store",
        lambda: {
            f"{counter}.delta": (
                0,
                _extract_value_to_mock_for_zero_growth(expected_result),
            )
        },
    )
    assert list(df.check_df(item, params, parse_df(info))) == expected_result


# .
#   .--groups--------------------------------------------------------------.
#   |                                                                      |
#   |                    __ _ _ __ ___  _   _ _ __  ___                    |
#   |                   / _` | '__/ _ \| | | | '_ \/ __|                   |
#   |                  | (_| | | | (_) | |_| | |_) \__ \                   |
#   |                   \__, |_|  \___/ \__,_| .__/|___/                   |
#   |                   |___/                |_|                           |
#   '----------------------------------------------------------------------'

info_df_groups = [
    ["/dev/sda1", "ext4", "100", "60", "10", "1%", "/"],
    ["/dev/sda2", "ext4", "110", "61", "11", "2%", "/foo"],
    ["/dev/sda3", "ext4", "120", "62", "12", "3%", "/bar"],
    ["/dev/sdb1", "btrfs", "130", "63", "13", "4%", "/one"],
    ["/dev/sdb1", "btrfs", "130", "63", "13", "4%", "/two"],
]


@pytest.mark.parametrize(
    "inventory_df_rules, expected_result",
    [
        # no groups
        (
            {},
            [
                (
                    "/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/foo",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/bar",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "btrfs /dev/sdb1",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "mountpoint",
            },
            [
                (
                    "/",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/foo",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/bar",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "btrfs /dev/sdb1",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
            },
            [
                (
                    "/dev/sda1 /",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda2 /foo",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
            },
            [
                (
                    "/dev/sda1 /",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda2 /foo",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        # groups
        (
            {
                "groups": [
                    {
                        "group_name": "my-group",
                        "patterns_include": ["/", "/foo"],
                        "patterns_exclude": ["/bar"],
                    }
                ]
            },
            [
                (
                    "my-group",
                    {
                        "item_appearance": "mountpoint",
                        "grouping_behaviour": "mountpoint",
                        "patterns": (["/", "/foo"], ["/bar"]),
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/bar",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "btrfs /dev/sdb1",
                    {
                        "item_appearance": "mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "groups": [
                    {
                        "group_name": "my-group",
                        "patterns_include": ["/", "/foo"],
                        "patterns_exclude": ["/bar"],
                    }
                ],
            },
            [
                (
                    "my-group",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "grouping_behaviour": "mountpoint",
                        "patterns": (["/", "/foo"], ["/bar"]),
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                # groups do not apply
                "groups": [
                    {
                        "group_name": "my-group",
                        "patterns_include": ["/dev/sda1 /", "/dev/sda2 /foo"],
                        "patterns_exclude": ["/dev/sda3 /bar"],
                    }
                ],
            },
            [
                (
                    "/dev/sda1 /",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda2 /foo",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                "groups": [
                    {
                        "group_name": "my-group",
                        "patterns_include": ["/dev/sda1 /", "/dev/sda2 /foo"],
                        "patterns_exclude": ["/dev/sda3 /bar"],
                    }
                ],
            },
            [
                (
                    "my-group",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "grouping_behaviour": "volume_name_and_mountpoint",
                        "patterns": (["/dev/sda1 /", "/dev/sda2 /foo"], ["/dev/sda3 /bar"]),
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                # groups do not apply
                "groups": [
                    {
                        "group_name": "my-group",
                        "patterns_include": ["/", "/foo"],
                        "patterns_exclude": ["/bar"],
                    }
                ],
            },
            [
                (
                    "/dev/sda1 /",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda2 /foo",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sda3 /bar",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
                (
                    "/dev/sdb1 btrfs /dev/sdb1",
                    {
                        "item_appearance": "volume_name_and_mountpoint",
                        "mountpoint_for_block_devices": "volume_name",
                    },
                ),
            ],
        ),
    ],
)
def test_df_discovery_groups_with_parse(  # type:ignore[no-untyped-def]
    inventory_df_rules, expected_result
) -> None:
    assert sorted(df.discover_df(inventory_df_rules, parse_df(info_df_groups))) == sorted(
        Service(item=i, parameters=p) for i, p in expected_result
    )


@pytest.mark.parametrize(
    "add_params, expected_result",
    [
        (
            {
                "grouping_behaviour": "mountpoint",
                "patterns": (["/", "/foo"], ["/bar"]),
            },
            [
                Metric(
                    "fs_used",
                    0.1845703125,
                    levels=(0.1640625, 0.1845703125),
                    boundaries=(0.0, 0.205078125),
                ),
                Metric("fs_free", 0.0205078125, boundaries=(0.0, None)),
                Metric("fs_used_percent", 90.0, levels=(80.0, 90.0), boundaries=(0.0, 100.0)),
                Result(
                    state=State.CRIT,
                    summary="Used: 90.00% - 189 KiB of 210 KiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_size", 0.205078125, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 0.008544921875)),
                Result(state=State.OK, summary="2 filesystems"),
            ],
        ),
        (
            {
                "item_appearance": "mountpoint",
                "grouping_behaviour": "mountpoint",
                "patterns": (["/", "/foo"], ["/bar"]),
            },
            [
                Metric(
                    "fs_used",
                    0.1845703125,
                    levels=(0.1640625, 0.1845703125),
                    boundaries=(0.0, 0.205078125),
                ),
                Metric("fs_free", 0.0205078125, boundaries=(0.0, None)),
                Metric("fs_used_percent", 90.0, levels=(80.0, 90.0), boundaries=(0.0, 100.0)),
                Result(
                    state=State.CRIT,
                    summary="Used: 90.00% - 189 KiB of 210 KiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_size", 0.205078125, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 0.008544921875)),
                Result(state=State.OK, summary="2 filesystems"),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                "patterns": (["/dev/sda1 /", "/dev/sda2 /foo"], ["/dev/sda3 /bar"]),
            },
            [
                Metric(
                    "fs_used",
                    0.1845703125,
                    levels=(0.1640625, 0.1845703125),
                    boundaries=(0.0, 0.205078125),
                ),
                Metric("fs_free", 0.0205078125, boundaries=(0.0, None)),
                Metric("fs_used_percent", 90.0, levels=(80.0, 90.0), boundaries=(0.0, 100.0)),
                Result(
                    state=State.CRIT,
                    summary="Used: 90.00% - 189 KiB of 210 KiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_size", 0.205078125, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 0.008544921875)),
                Result(state=State.OK, summary="2 filesystems"),
            ],
        ),
        # unknowns; only happens if patterns are adapted without discovery
        (
            {
                "item_appearance": "mountpoint",
                "grouping_behaviour": "mountpoint",
                "patterns": (["/dev/sda1 /", "/dev/sda2 /foo"], ["/dev/sda3 /bar"]),
            },
            [
                Result(state=State.UNKNOWN, summary="No filesystem matching the patterns"),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                "patterns": (["/", "/foo"], ["/bar"]),
            },
            [
                Result(state=State.UNKNOWN, summary="No filesystem matching the patterns"),
            ],
        ),
        # mixed btrfs and mps
        (
            {
                "item_appearance": "mountpoint",
                "grouping_behaviour": "mountpoint",
                "patterns": (["/", "btrfs /dev/sdb1"], ["/foo", "/bar"]),
            },
            [
                Metric(
                    "fs_used",
                    0.2021484375,
                    levels=(0.1796875, 0.2021484375),
                    boundaries=(0.0, 0.224609375),
                ),
                Metric("fs_free", 0.0224609375, boundaries=(0.0, None)),
                Metric("fs_used_percent", 90.0, levels=(80.0, 90.0), boundaries=(0.0, 100.0)),
                Result(
                    state=State.CRIT,
                    summary="Used: 90.00% - 207 KiB of 230 KiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_size", 0.224609375, boundaries=(0.0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 0.009358723958333334)),
                Result(state=State.OK, summary="2 filesystems"),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                "patterns": (
                    ["/dev/sda1 /", "/dev/sdb1 btrfs /dev/sdb1"],
                    ["/dev/sda2 /foo", "/dev/sda3 /bar"],
                ),
            },
            [
                Metric(
                    "fs_used",
                    0.2021484375,
                    levels=(0.1796875, 0.2021484375),
                    boundaries=(0.0, 0.224609375),
                ),
                Metric("fs_free", 0.0224609375, boundaries=(0, None)),
                Metric("fs_used_percent", 90.0, levels=(80.0, 90.0), boundaries=(0.0, 100.0)),
                Result(
                    state=State.CRIT,
                    summary="Used: 90.00% - 207 KiB of 230 KiB (warn/crit at 80.00%/90.00% used)",
                ),
                Metric("fs_size", 0.224609375, boundaries=(0, None)),
                Metric("growth", 0.0),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0 B"),
                Result(state=State.OK, summary="trend per 1 day 0 hours: +0%"),
                Metric("trend", 0.0, boundaries=(0.0, 0.009358723958333334)),
                Result(state=State.OK, summary="2 filesystems"),
            ],
        ),
        # unknowns; only happens if patterns are adapted without discovery
        (
            {
                "item_appearance": "mountpoint",
                "grouping_behaviour": "mountpoint",
                "patterns": (
                    ["/dev/sda1 /", "/dev/sdb1 btrfs /dev/sdb1"],
                    ["/dev/sda2 /foo", "/dev/sda3 /bar"],
                ),
            },
            [
                Result(state=State.UNKNOWN, summary="No filesystem matching the patterns"),
            ],
        ),
        (
            {
                "item_appearance": "volume_name_and_mountpoint",
                "grouping_behaviour": "volume_name_and_mountpoint",
                "patterns": (["/", "btrfs /dev/sdb1"], ["/foo", "/bar"]),
            },
            [Result(state=State.UNKNOWN, summary="No filesystem matching the patterns")],
        ),
    ],
)
def test_df_check_groups_with_parse(  # type:ignore[no-untyped-def]
    add_params, expected_result, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        df,
        "get_value_store",
        lambda: {"my-group.delta": (0, _extract_value_to_mock_for_zero_growth(expected_result))},
    )
    assert (
        list(
            df.check_df(
                "my-group", {**make_test_df_params(), **add_params}, parse_df(info_df_groups)
            )
        )
        == expected_result
    )
